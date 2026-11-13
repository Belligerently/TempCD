//! Exercise real REPLs rather than `nu -c`, which does not run interactive hooks.
#[cfg(unix)]
#[test]
fn interactive_shells() {
    let python = std::env::var("PYTHON").unwrap_or_else(|_| "python3".into());
    let status = std::process::Command::new(python)
        .arg("tests/repl.py")
        .env("TCD_BIN", env!("CARGO_BIN_EXE_tcd"))
        .status()
        .expect("interactive tests need Python 3 (standard library only)");
    assert!(
        status.success(),
        "interactive shell integration tests failed"
    );
}
