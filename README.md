# TempCD

TempCD provides the `tcd` command.

Visit a directory for **one interactive command**, then return before the next
prompt. Opt in with `tcd`; normal `cd` is untouched.

```text
~> tcd ~/projects/copse
~/projects/copse> cargo test
…test output…
~>
```

The return location is where you ran `tcd`, not necessarily your home directory.
MIT licensed. Rust executable, no third-party dependencies, no daemon, and no
per-command subprocess overhead. The Rust package has not been published to
crates.io.

## Runtime and reliability

**Python is not required to install or use TempCD.** The Rust executable
generates self-contained Nushell or Zsh integration. That shell code performs
the directory changes and automatic return; it does not launch Python or Rust
for each command. Python is used only by the development tests to drive real
interactive terminals, using its standard library.

This is an **early v0.2 release**: 3 Rust unit tests and 57 interactive cases
passed locally on macOS. The previous version also passed [Linux CI](https://github.com/Belligerently/TempCD/actions/runs/43352689754).
See [validation](VALIDATION.md) for the current results.
Those checks cover the core workflow and edge cases, but do not establish
compatibility with every shell configuration. Prompt and environment hooks are
the main integration boundary: replacing hook lists can disable TempCD, and a
hook that aborts the execution cycle can prevent a return. See the support and
boundaries below for tested versions and limitations.

## Install from this source

Download or clone [TempCD](https://github.com/Belligerently/TempCD).

Requires Rust/Cargo 1.74+ and one of the tested shells below. In the unpacked
project directory:

```sh
cargo install --path . --locked
```

Ensure Cargo's bin directory (usually `~/.cargo/bin`) is on your PATH.
The executable **cannot change its parent shell's directory**. Load the real
shell integration next; running the executable with a path reports a setup error.

### Nushell (primary)

Run once in Nu, **after installing the executable**:

```nu
^tcd init nu | save --force ($nu.default-config-dir | path join 'tcd.nu')
```

Add this to `config.nu` (open it with `config nu`), after your existing hook setup:

```nu
source ($nu.default-config-dir | path join 'tcd.nu')
```

Open a new shell. Do not put `tcd some-directory` in your startup file: it is an
interactive operation. For a temporary trial without installing, from this
project directory use `source shells/tcd.nu` in an existing interactive Nu.
To regenerate the integration after an upgrade, use **`^tcd`**, since `tcd` now
names the shell function. The generated file is self-contained.

### Zsh

Add to `.zshrc`, after your prompt and hook setup:

```zsh
eval "$(command tcd init zsh)"
```

Alternatively, source `shells/tcd.zsh` by absolute path. `command tcd` selects the
executable even after the function is installed. Re-sourcing either integration
does not duplicate hooks or discard pending visits.

## Behavior

- Use two separate entered lines: `tcd 'path with spaces'`, then your command.
  The entire next submitted line is the unit of work: pipelines, compound
  commands, and multiline constructs finish together. `tcd dir; command` on
  the **same** submitted line does not count as the two-command workflow.
- Failed external commands, shell errors, unknown commands, and interrupted
  foreground commands still return. Command output streams normally. The
  integration preserves the external exit code in Nu and prompt status in Zsh.
  Other user hooks can independently change those statuses.
- Blank input, prompt redraws, and canceling an unsubmitted edit do not spend
  the visit. Hook commands do not count as entered commands.
- Nested visits unwind one level per subsequent command:
  `tcd A` → `tcd B` → command in B → back to A → command in A → back to origin.
  A failed nested `tcd` consumes the outer visit and returns to its origin.
- `tcd --cancel` disarms **all** pending returns and stays where you are.
- `tcd --status` shows the next return directory and nesting depth. It leaves
  you in place and does **not** consume the visit, so the next ordinary command
  still runs in the destination. With no visit, it reports `no pending return`.
- `tcd --back` returns immediately, unwinding **one** visit. If an outer visit
  remains, the next ordinary command consumes that visit. With no visit, it
  reports an error. A failed return clears the entire pending stack.
- Use each control on its own submitted line, without a directory or another
  control flag. For example, `tcd --status; command` keeps the visit pending
  for that whole line; status inspection is not a command-counting mechanism.
- If a command or hook changes cwd away from the current destination, the
  pending stack is canceled. An explicit `cd` therefore wins. Hooks that run
  after restoration can also choose a new cwd. A change away and back to the
  exact same path is indistinguishable from staying there.
- If the original directory is gone or inaccessible, tcd reports the failed
  return, stays put, and clears the stack. It never retries at later prompts.
- Paths are passed as data to shell built-ins, never interpolated into code.
  Each shell retains its own path expansion semantics. Quote spaces as usual.

## Support and boundaries

| Shell | Status |
| --- | --- |
| Nushell | Tested on 0.116.1, macOS arm64, using real interactive PTYs |
| Zsh | Tested on 5.9, macOS arm64, using real interactive PTYs |
| Bash | Not implemented; the available 3.2 lacks a native pre-execution hook. A DEBUG-trap implementation needs separate compatibility work. |
| Fish | Not implemented or tested; Fish was unavailable in the build environment. |
| PowerShell | Not implemented or tested; PowerShell/PSReadLine was unavailable. |

The interactive suite also passed on the GitHub-hosted Ubuntu runner with
Nushell 0.116.1 and the runner's installed Zsh. Windows has not been verified.
Compatibility with other shell versions and custom hook setups is not guaranteed.

These are interactive integrations. Nu's hooks do not run in `nu -c` or scripts;
use ordinary `cd` or a scoped/subshell command in scripts. Do not call `tcd`
from prompt/environment hooks. Existing hooks are retained, but replacing their
lists after installation removes tcd's callbacks; restart the shell after fixing
configuration order. A hook that aborts the shell's hook cycle can prevent a
return. Arbitrary hook code cannot be sandboxed by tcd.

An `exit`, `exec`, shell crash, or enabled exit-on-error option that terminates
the shell prevents a subsequent prompt and thus a return. Background commands
consume the submitted line as soon as they launch; tcd does not wait for jobs.
Directory restoration uses `cd`, so normal shell directory-change hooks still
run and Nu's previous-directory history / Zsh's `OLDPWD` can change.

To uninstall, remove the configuration line, open a new shell, delete the
generated integration file if used, then run `cargo uninstall tcd`.

### Upgrade to v0.2

Reinstall from the updated source with `cargo install --path . --locked --force`.
In Nu, regenerate the integration with the `^tcd init nu | save --force ...`
command above, then open a new shell. Zsh's configuration loads the updated
integration when you open a new shell. Restarting also avoids mixing old
registered callbacks with newly sourced functions.

## Develop and verify

```sh
cargo fmt --check
cargo clippy --offline --all-targets -- -D warnings
cargo test --offline
```

Interactive tests need POSIX, Python 3 (standard library only), and the target
shells on PATH. Missing shells are visibly skipped. Set `TCD_REQUIRE_SHELLS=1`
to fail instead of skipping either Nu or Zsh. Windows currently runs Rust tests
only. `PYTHON` can select the Python executable.

The PTY suite enters actual lines and checks cwd at the following prompt, plus
files written inside the visited directory. It covers success, failure/status,
unknown commands, paths with spaces/punctuation/Unicode, relative paths, tilde,
nesting, cancellation, explicit cd, setup/re-sourcing, command-running and
directory-changing hooks, missing origins, blank lines, Ctrl-C while editing
and running, child Nu initialization, pipelines, and a real `cargo test` fixture.
See [tests/repl.py](tests/repl.py). Shell behavior is implemented in
[shells/tcd.nu](shells/tcd.nu) and [shells/tcd.zsh](shells/tcd.zsh); the Rust CLI
embeds and emits those files verbatim.

Hook API references: [Nushell hooks](https://www.nushell.sh/book/hooks.html),
[Zsh hook functions](https://zsh.sourceforge.io/Doc/Release/Functions.html), and
[add-zsh-hook](https://zsh.sourceforge.io/Doc/Release/User-Contributions.html#Manipulating-Hook-Functions).
