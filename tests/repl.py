"""Real interactive shells over a controlling PTY; no mocked hook invocations.

Python's standard library is the only test dependency. Run via cargo test or
TCD_BIN=target/debug/tcd python3 tests/repl.py. POSIX only.
"""
import errno
import fcntl
import os
from pathlib import Path
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import tempfile
import termios
import time
import unittest

BIN = str(Path(os.environ.get("TCD_BIN", "target/debug/tcd")).resolve())
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
PROMPT = re.compile(r"__TCD_PROMPT_(\d+)__(.*?)__STATUS_(-?\d+)__END__")


def quote(text):
    # Single-quoted literal syntax shared by Nu and Zsh, without interpolation.
    # Our generated paths never contain an apostrophe. Tests use double quotes
    # for the explicit apostrophe case.
    assert "'" not in str(text)
    return "'" + str(text) + "'"


class Repl:
    def __init__(self, shell, root, extra=""):
        self.shell = shell
        self.buffer = ""
        self.sequence = 0
        integration = subprocess.check_output([BIN, "init", shell], text=True)
        config = root / ("config.nu" if shell == "nu" else ".zshrc")
        if shell == "nu":
            (root / "tcd.nu").write_text(integration)
            integration = "source ($nu.default-config-dir | path join 'tcd.nu')\n"
            integration += """
$env.config.show_banner = false
$env.config.shell_integration.osc133 = false
$env.config.shell_integration.osc2 = false
$env.config.use_kitty_protocol = false
$env.config.error_style = 'plain'
$env.PROMPT_COMMAND_RIGHT = ''
$env.PROMPT_INDICATOR = ''
$env.PROMPT_MULTILINE_INDICATOR = ''
$env.__TEST_SEQ = 0
$env.config.hooks.pre_prompt = ($env.config.hooks.pre_prompt | append {||
    $env.__TEST_SEQ = $env.__TEST_SEQ + 1
})
$env.PROMPT_COMMAND = {||
    $"__TCD_PROMPT_($env.__TEST_SEQ)__($env.PWD)__STATUS_($env.LAST_EXIT_CODE? | default 0)__END__ "
}
"""
            args = [shutil.which("nu"), "-n", "--config-home", str(root), "--no-history", "-e", "source " + quote(config)]
            (root / "env.nu").write_text("")
        else:
            integration += """
setopt PROMPT_SUBST
unsetopt PROMPT_SP PROMPT_CR
_test_seq=0
function precmd() { (( ++_test_seq )); }
PS1='__TCD_PROMPT_${_test_seq}__%/__STATUS_%?__END__ '
RPROMPT=''
"""
            args = [shutil.which("zsh"), "-d", "-i"]
        config.write_text(integration + "\n" + extra)
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(root)
            os.environ.update(TERM="xterm-256color", ZDOTDIR=str(root), NO_COLOR="1")
            os.execv(args[0], args)
        self.pid, self.fd = pid, fd
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 160, 0, 0))
        try:
            self.prompt()
        except BaseException:
            self.close()
            raise

    def prompt(self, timeout=12):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            readable, _, _ = select.select([self.fd], [], [], 0.1)
            if readable:
                try:
                    data = os.read(self.fd, 65536)
                except OSError as error:
                    if error.errno == errno.EIO:
                        break
                    raise
                if not data:
                    break
                self.buffer += data.decode("utf-8", errors="replace")
                # Reedline asks the terminal for its cursor position.
                if b"\x1b[6n" in data:
                    os.write(self.fd, b"\x1b[1;1R")
                plain = ANSI.sub("", self.buffer)
                matches = [m for m in PROMPT.finditer(plain) if int(m[1]) > self.sequence]
                if matches:
                    m = matches[-1]
                    self.sequence = int(m[1])
                    self.cwd, self.status = m[2], int(m[3])
                    # Prompt text can arrive before the line editor enters raw mode.
                    time.sleep(0.02)
                    return plain
        raise AssertionError("No next prompt; terminal output:\n" + repr(self.buffer[-12000:]))

    def run(self, line):
        self.buffer = ""
        os.write(self.fd, line.encode() + b"\r")
        return self.prompt()

    def settle(self):
        # Drain redraws/empty-input prompts without requiring a new hook cycle.
        end = time.monotonic() + 0.2
        while time.monotonic() < end:
            if select.select([self.fd], [], [], 0.02)[0]:
                data = os.read(self.fd, 65536)
                self.buffer += data.decode("utf-8", errors="replace")
                if b"\x1b[6n" in data:
                    os.write(self.fd, b"\x1b[1;1R")
        matches = list(PROMPT.finditer(ANSI.sub("", self.buffer)))
        if matches:
            m = matches[-1]
            self.sequence, self.cwd, self.status = int(m[1]), m[2], int(m[3])

    def close(self):
        try:
            os.kill(self.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        os.close(self.fd)
        os.waitpid(self.pid, 0)


class InteractiveCases:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tcd-repl-")
        self.root = Path(self.temp.name).resolve()
        self.a = self.root / "project with spaces"
        self.b = self.a / "child"
        self.b.mkdir(parents=True)
        self.repl = None

    def tearDown(self):
        if self.repl:
            self.repl.close()
        self.temp.cleanup()

    def start(self, extra=""):
        self.repl = Repl(self.shell, self.root, extra)
        return self.repl

    def visit(self, path=None):
        self.repl.run("tcd " + quote(path or self.a))
        self.assertEqual(self.repl.cwd, str(path or self.a))

    def test_success_and_single_return(self):
        r = self.start()
        self.visit()
        r.run("pwd | save -f result.txt" if self.shell == "nu" else "pwd > result.txt")
        self.assertEqual((self.a / "result.txt").read_text().strip(), str(self.a))
        self.assertEqual(r.cwd, str(self.root))
        r.run("cd " + quote(self.a))
        r.run("echo ordinary-cd")
        self.assertEqual(r.cwd, str(self.a))

    def test_external_failure_preserves_status(self):
        r = self.start()
        self.visit()
        r.run("sh -c 'exit 7'")
        self.assertEqual(r.cwd, str(self.root))
        self.assertEqual(r.status, 7)

    def test_error_and_unknown_command(self):
        r = self.start()
        for command in ["error make {msg: 'oops'}" if self.shell == "nu" else "false", "tcd_nonexistent_command_12345"]:
            self.visit()
            r.run(command)
            self.assertEqual(r.cwd, str(self.root))

    def test_invalid_destination(self):
        r = self.start()
        r.run("tcd " + quote(self.root / "missing"))
        self.assertEqual(r.cwd, str(self.root))
        r.run("cd " + quote(self.a))
        r.run("echo still-here")
        self.assertEqual(r.cwd, str(self.a))

    def test_nested_visits_unwind_one_at_a_time(self):
        r = self.start()
        self.visit()
        self.visit(self.b)
        r.run("echo inner")
        self.assertEqual(r.cwd, str(self.a))
        r.run("echo outer")
        self.assertEqual(r.cwd, str(self.root))

    def test_explicit_cd_cancels(self):
        r = self.start()
        self.visit()
        r.run("cd child")
        self.assertEqual(r.cwd, str(self.b))
        r.run("echo stay")
        self.assertEqual(r.cwd, str(self.b))

    def test_cancel(self):
        r = self.start()
        self.visit()
        r.run("tcd --cancel")
        r.run("echo stay")
        self.assertEqual(r.cwd, str(self.a))

    def test_source_twice(self):
        r = self.start()
        init = self.root / ("again.nu" if self.shell == "nu" else "again.zsh")
        init.write_text(subprocess.check_output([BIN, "init", self.shell], text=True))
        r.run("source " + quote(init))
        self.visit()
        self.visit(self.b)
        r.run("echo inner")
        self.assertEqual(r.cwd, str(self.a))
        r.run("echo outer")
        self.assertEqual(r.cwd, str(self.root))

    def test_setup_does_not_arm(self):
        r = self.start("tcd " + quote(self.a) + "\n")
        self.assertEqual(r.cwd, str(self.root))
        r.run("echo harmless")
        self.assertEqual(r.cwd, str(self.root))

    def test_prompt_commands_do_not_consume_visit(self):
        if self.shell == "nu":
            extra = "$env.config.hooks.pre_prompt = ($env.config.hooks.pre_prompt | append {|| sh -c 'exit 0' })\n"
        else:
            extra = "function _test_extra() { command true; }; precmd_functions+=(_test_extra)\n"
        r = self.start(extra)
        self.visit()
        r.run("echo actual-command")
        self.assertEqual(r.cwd, str(self.root))

    def test_missing_origin_disarms_without_retry(self):
        origin = self.root / "disappearing"
        origin.mkdir()
        r = self.start()
        r.run("cd " + quote(origin))
        self.visit()
        origin.rmdir()
        output = r.run("echo finish")
        self.assertIn("could not return", output)
        self.assertEqual(r.cwd, str(self.a))
        origin.mkdir()
        r.run("echo no-retry")
        self.assertEqual(r.cwd, str(self.a))

    def test_pipeline_is_one_line(self):
        r = self.start()
        self.visit()
        r.run("echo hello | str upcase | save -f pipeline.txt" if self.shell == "nu" else "echo hello | tr a-z A-Z > pipeline.txt")
        self.assertEqual((self.a / "pipeline.txt").read_text().strip(), "HELLO")
        self.assertEqual(r.cwd, str(self.root))

    def test_literal_path_and_relative_path(self):
        unusual = self.root / "quote' $dollar; [brackets] café"
        unusual.mkdir()
        r = self.start()
        # Single quotes in a double-quoted literal; escape Zsh expansion only.
        path = str(unusual).replace("$", "\\$") if self.shell == "zsh" else str(unusual)
        r.run('tcd "' + path + '"')
        self.assertEqual(r.cwd, str(unusual))
        r.run("echo literal")
        self.assertEqual(r.cwd, str(self.root))
        r.run("tcd 'project with spaces'")
        self.assertEqual(r.cwd, str(self.a))
        r.run("echo relative")
        self.assertEqual(r.cwd, str(self.root))

    def test_failed_nested_visit_returns_outer(self):
        r = self.start()
        self.visit()
        r.run("tcd does-not-exist")
        self.assertEqual(r.cwd, str(self.root))

    def test_hook_directory_change_cancels(self):
        if self.shell == "nu":
            hook = "{|| if $env.PWD == " + quote(self.a) + " { cd " + quote(self.b) + " } }"
            extra = "$env.config.hooks.pre_prompt = ($env.config.hooks.pre_prompt | prepend " + hook + ")\n"
        else:
            extra = "function _move_prompt() { if [[ $PWD == " + quote(self.a) + " ]]; then builtin cd " + quote(self.b) + "; fi; }; precmd_functions=(_move_prompt $precmd_functions)\n"
        r = self.start(extra)
        r.run("tcd " + quote(self.a))
        self.assertEqual(r.cwd, str(self.b))
        r.run("echo no-surprise-return")
        self.assertEqual(r.cwd, str(self.b))

    def test_late_hook_directory_change_cancels_before_next_visit(self):
        if self.shell == "nu":
            extra = "$env.config.hooks.pre_prompt = ($env.config.hooks.pre_prompt | append {|| if $env.PWD == " + quote(self.a) + " { cd " + quote(self.b) + " } })\n"
        else:
            extra = "function _move_prompt() { if [[ $PWD == " + quote(self.a) + " ]]; then builtin cd " + quote(self.b) + "; fi; }; precmd_functions+=(_move_prompt)\n"
        destination = self.root / "elsewhere"
        destination.mkdir()
        r = self.start(extra)
        r.run("tcd " + quote(self.a))
        self.assertEqual(r.cwd, str(self.b))
        self.visit(destination)
        r.run("echo finish")
        self.assertEqual(r.cwd, str(self.b))
        r.run("echo no-stale-outer")
        self.assertEqual(r.cwd, str(self.b))

    def test_blank_line_and_edit_interrupt_do_not_consume(self):
        r = self.start()
        self.visit()
        os.write(r.fd, b"\r")
        r.settle()
        # Blank lines/redraws need not increment the shell's prompt sequence.
        self.assertEqual(r.cwd, str(self.a))
        os.write(r.fd, b"echo never-execute\x03")
        r.settle()
        r.run("pwd > interrupted.txt" if self.shell == "zsh" else "pwd | save -f interrupted.txt")
        self.assertTrue((self.a / "interrupted.txt").exists())
        self.assertEqual(r.cwd, str(self.root))

    def test_running_command_interrupt_returns(self):
        r = self.start()
        self.visit()
        r.buffer = ""
        os.write(r.fd, b"sh -c 'touch interrupt-started; exec sleep 10'\r")
        r.settle()
        deadline = time.monotonic() + 3
        while not (self.a / "interrupt-started").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue((self.a / "interrupt-started").exists(), "command must start before interrupt")
        os.write(r.fd, b"\x03")
        r.prompt()
        self.assertEqual(r.cwd, str(self.root))

    def test_tilde_expansion(self):
        r = self.start()
        r.run("tcd ~")
        self.assertEqual(r.cwd, str(Path.home().resolve()))
        r.run("echo home-visit")
        self.assertEqual(r.cwd, str(self.root))

    def test_real_cargo_test(self):
        if not shutil.which("cargo"):
            self.skipTest("cargo not installed")
        (self.a / "Cargo.toml").write_text('[package]\nname="tcd-repl-fixture"\nversion="0.0.0"\nedition="2021"\n')
        (self.a / "src").mkdir()
        (self.a / "src/lib.rs").write_text('#[test] fn cwd() { std::fs::write("cargo-test-ran", std::env::current_dir().unwrap().to_str().unwrap()).unwrap(); }\n')
        r = self.start()
        self.visit()
        r.run("cargo test --offline --quiet")
        self.assertEqual(r.status, 0)
        self.assertEqual((self.a / "cargo-test-ran").read_text(), str(self.a))
        self.assertEqual(r.cwd, str(self.root))


@unittest.skipUnless(shutil.which("nu"), "Nushell not installed")
class Nushell(InteractiveCases, unittest.TestCase):
    shell = "nu"

    def test_child_nu_reinitializes_inherited_state(self):
        script = self.root / "child.nu"
        integration = self.root / "integration.nu"
        integration.write_text(subprocess.check_output([BIN, "init", "nu"], text=True))
        script.write_text("source " + quote(integration) + '\nif $env.__TCD_OWNER != $nu.pid { error make {msg: "wrong owner"} }\nprint child-ok\n')
        r = self.start()
        self.visit()
        r.run("nu -n " + quote(script) + " | save -f child.txt")
        self.assertEqual((self.a / "child.txt").read_text().strip(), "child-ok")
        self.assertEqual(r.cwd, str(self.root))


@unittest.skipUnless(shutil.which("zsh"), "Zsh not installed")
class Zsh(InteractiveCases, unittest.TestCase):
    shell = "zsh"


if __name__ == "__main__":
    if os.environ.get("TCD_REQUIRE_SHELLS"):
        for shell in ("nu", "zsh"):
            if not shutil.which(shell):
                raise SystemExit("Required shell missing: " + shell)
    unittest.main(verbosity=2)
