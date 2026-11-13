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
Shell controls: tcd --status | tcd --back | tcd --cancel\n\
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
    let args: Vec<_> = std::env::args().skip(1).collect();
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

#[cfg(test)]
mod tests {
    use super::*;
    fn run(args: &[&str]) -> Result<&'static str, &'static str> {
        output(&args.iter().map(|s| s.to_string()).collect::<Vec<_>>())
    }
    #[test]
    fn static_integrations() {
        assert_eq!(run(&["init", "nu"]), run(&["init", "nushell"]));
        assert!(run(&["init", "nu"]).unwrap().contains("def --env tcd"));
        assert!(run(&["init", "zsh"]).unwrap().contains("preexec"));
    }
    #[test]
    fn rejects_unsupported_shells_and_direct_cd() {
        for args in [
            vec!["init", "bash"],
            vec!["init", "fish"],
            vec!["init", "pwsh"],
            vec!["/tmp"],
            vec!["init"],
        ] {
            assert!(run(&args).is_err());
        }
    }
    #[test]
    fn help_and_version() {
        assert_eq!(run(&[]), run(&["--help"]));
        assert_eq!(run(&["--version"]).unwrap(), "tcd 0.2.0\n");
    }
}
