//! The executable installs shell code; only that code can change the parent cwd.
use std::io::{self, Write};
use std::process::ExitCode;

const HELP: &str = "tcd — visit a directory for one interactive command\n\n\
Usage: tcd init <nu|zsh>\n\
       tcd --help\n\
Load shell integration first (see README), then use:\n\
  tcd ~/projects/copse\n\
  cargo test\n\n\
The shell returns before the next prompt. Normal cd is unchanged.\n\
Shell controls: tcd --status [--json] | tcd --doctor | tcd --back | tcd --cancel\n\
The executable cannot change its parent shell's directory.\n";

fn output(args: &[String]) -> Result<&'static str, &'static str> {
    match args {
        [] => Ok(HELP),
        [flag] if flag == "--help" || flag == "-h" => Ok(HELP),
        [flag] if flag == "--version" || flag == "-V" => Ok(concat!("tcd ", env!("CARGO_PKG_VERSION"), "\n")),
        [cmd, shell] if cmd == "init" => match shell.as_str() {
            "nu" | "nushell" => Ok(include_str!("../shells/tcd.nu")),
            "zsh" => Ok(include_str!("../shells/tcd.zsh")),
            _ => Err("supported integrations: nu, zsh; Bash, Fish and PowerShell are not implemented"),
        },
        _ => Err("shell integration is required: run `tcd --help` and follow the README setup instructions"),
    }
}

fn main() -> ExitCode {
    let args: Result<Vec<_>, _> = std::env::args_os()
        .skip(1)
        .map(|arg| arg.into_string())
        .collect();
    let Ok(args) = args else {
        eprintln!("tcd: arguments must be valid UTF-8");
        return ExitCode::from(2);
    };
    match output(&args) {
        Ok(body) => match io::stdout().lock().write_all(body.as_bytes()) {
            Ok(()) => ExitCode::SUCCESS,
            // `tcd init nu | head` should not panic.
            Err(e) if e.kind() == io::ErrorKind::BrokenPipe => ExitCode::SUCCESS,
            Err(e) => {
                eprintln!("tcd: {e}");
                ExitCode::FAILURE
            }
        },
        Err(message) => {
            eprintln!("tcd: {message}");
            ExitCode::from(2)
        }
    }
}
