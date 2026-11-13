# Validation record

Verified locally on macOS arm64 with Rust/Cargo 1.98.1, Python 3.9.6,
Nushell 0.116.1 and Zsh 5.9.

- `cargo fmt --check`: passed.
- `cargo clippy --offline --locked --all-targets -- -D warnings`: passed.
- `TCD_REQUIRE_SHELLS=1 cargo test --offline --locked`: passed;
  3 Rust unit tests plus 41 real interactive PTY cases, no skipped shells.
- `cargo install --path . --locked --offline --root <temporary-directory>`:
  passed; installed executable reports `tcd 0.1.0` and emits integration files.
- The Nu PTY tests load the generated file using the exact `source` expression
  documented in the README. Both shells run an ordinary `cargo test` in a
  fixture project and return to the original cwd before the following prompt.

The [Linux CI run](https://github.com/Belligerently/TempCD/actions/runs/43352689754)
also passed on GitHub's Ubuntu runner, with both shells required. Bash, Fish,
PowerShell, Windows, and other shell versions are not claimed as verified.
No personal shell configuration was changed during validation.
