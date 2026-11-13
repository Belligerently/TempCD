# Validation record — v0.2.1

## v0.2.0 baseline and migration history

Verified locally on macOS arm64 with Rust/Cargo 1.98.1, Python 3.9.6,
Nushell 0.116.1 and Zsh 5.9.

- `cargo fmt --check`: passed.
- `cargo clippy --offline --locked --all-targets -- -D warnings`: passed.
- Original `TCD_REQUIRE_SHELLS=1 cargo test --offline --locked`: passed;
  3 Rust unit tests plus 57 real interactive PTY cases, no skipped shells.
- `cargo install --path . --locked --offline --root <temporary-directory>`:
  passed; installed executable reports `tcd 0.2.0` and emits integration files.
- The Nu PTY tests load the generated file using the exact `source` expression
  documented in the README. Both shells run an ordinary `cargo test` in a
  fixture project and return to the original cwd before the following prompt.

- New control cases cover repeated status inspection without consuming visits,
  nested return paths and depths, immediate return, one-level unwinding,
  inactive controls, failed return cleanup, and conflicting arguments.

The [v0.1 Linux CI run](https://github.com/Belligerently/TempCD/actions/runs/43352689754)
also passed on GitHub's Ubuntu runner, with both shells required. Current
v0.2 CI results are available under [Actions](https://github.com/Belligerently/TempCD/actions).
Bash, Fish,
PowerShell, Windows, and other shell versions are not claimed as verified.
No personal shell configuration was changed during validation.

## Testing/build migration inventory

Before removing the stored tests, the repository contained:

- `src/main.rs`: a `#[cfg(test)]` module with 3 Rust cases, testing integration
  aliases/content, unsupported shells and executable misuse, and help/version.
- `tests/repl.py`: 28 shared interactive methods run on both Nu and Zsh,
  plus one Nu-only child-session case (57 executions).
- `tests/interactive.rs`: the Cargo-to-Python launcher, requiring a successful
  interactive suite exit. No separate stored fixtures or build scripts existed.
- `.github/workflows/test.yml`: formatting, Clippy, and the old Cargo test entry.

The original Rust and Python test definitions were migrated into `scripts/test.py`
before their files were removed. The obsolete Rust-to-Python launcher was
replaced by direct Python process execution with failure-status propagation.
All original Rust assertions and every Python assertion remain, and all 29
Python test methods are retained. Repeated visit setup now uses one helper.
Application code outside the test module and both shell files were preserved.

| Preserved coverage | Expected behavior | Cases |
| --- | --- | ---: |
| Rust CLI | Same Nu aliases, emitted integration content, rejected unsupported shells/direct cd, matching help and version | 3 |
| Basic visits, errors, nesting, explicit cd, cancel | Commands run in the destination; return once, preserve failure status, unwind one level, or respect cancellation | 14 |
| Status/back controls and invalid combinations | Inspect without consuming; report correct depth; return one level; fail safely and clear unusable returns | 16 |
| Setup, re-sourcing, command-running hooks | No startup visit, no duplicate hooks, no premature return | 6 |
| Other interactive edge cases | Missing origins disarm, pipelines finish, literal/relative/tilde paths work, failed nesting returns, directory hooks win, blank/edit interrupts preserve visits, running interrupts return, real cargo tests execute in place | 20 |
| Child Nu initialization | Child session reinitializes inherited state and parent returns normally | 1 |

The generator adds test-only Rust code to a disposable copy of `src/main.rs`
and writes the deterministic Python suite as `repl.py` in that workspace.
Python runs Cargo's unit tests, builds the real CLI, and launches the PTY suite
directly. Fixtures and test build output stay inside the workspace; only ignored
diagnostic logs survive. CI uses the test runner plus direct Cargo builds.

Optimization verification before the bug review, on the same macOS toolchain:

- The test runner shrank from 659 to 612 lines by removing the redundant Rust
  launcher, consolidating repeated test setup, and simplifying logging and
  orchestration. No assertions or scenarios were removed.
- `python3 scripts/test.py`: passed twice with 3 Rust tests and all 57
  interactive cases, with no skips. Generated workspaces were removed.
- A deliberately failing generated Python assertion verified that the runner
  returns nonzero, retains diagnostics, and removes its temporary workspace.
  This probe was injected only in memory and is not part of the test definitions.
- `cargo build --release --locked` and `cargo build --locked`: passed;
  executables and caches remain in `target/`. The redundant build script was removed.
- Formatting, Clippy with warnings denied, and `git diff --check` passed.
  Rust test definitions and Python assertion ASTs matched the previous runner;
  all 29 test methods remained. Shell files were byte-identical, and production
  Rust code matched after removing the test module (apart from trailing whitespace).
- All recorded temporary workspaces were checked and no longer existed.
  Existing `/target/` ignore rules cover logs and artifacts. No commit was created.

The new script workflow has been verified locally on macOS only. Its updated
Linux CI workflow has not run yet, and Windows remains unverified. Windows
can run the generated Rust tests; interactive shell coverage requires POSIX.

## Local bug review

Confirmed before editing the implementation:

- Nu returned after comment-only input following `tcd`, without an ordinary
  command executing. Zsh retained the visit with interactive comments enabled.
- A non-UTF-8 executable argument caused a Rust panic and exit 101.
- Nu returned after a syntax error; Zsh retained its visit. The difference
  follows hook execution order and is now documented rather than hidden.

Fixes ignore whitespace/comment-only Nu input and handle invalid Unicode
arguments as usage errors (stderr and exit 2). Added regression and process
checks bring coverage to **67 cases**: 3 original Rust unit tests, 61 shell
cases, and 3 CLI process cases. All original scenarios and assertions remain.
The suite passed on macOS with no skips and removed its generated workspace.

Formatting, Clippy with warnings denied, direct release/debug Cargo builds,
and diff checks also passed. The fixes and test workflow were verified locally; their Linux and Windows
behavior had not been verified during this review. See [REVIEW.md](REVIEW.md) for limitations and prioritized proposals.

## v0.2.1 feature validation

- Version updated in Cargo metadata, lockfile, generated integrations, CLI help,
  and the version assertion.
- `python3 scripts/test.py`: passed twice with 3 Rust unit tests and 82 Python cases
  (77 shell cases and 5 executable/helper cases), with no skips. All temporary
  workspaces were removed. Existing scenarios and assertions remain covered.
- New cases cover healthy and broken doctor output, duplicate/missing callbacks,
  version mismatch, preserving a visit on diagnostic failure, JSON status for
  idle/nested visits, rejected flag combinations, pure status hooks, and the
  optional prompt prefix while visiting and returning through nested directories.
- Codec checks verify JSON escaping and sanitized prompt text for quotes,
  backslashes, tabs, newlines, escape characters, Unicode, and percent signs.
  Literal command-like path text does not execute. Pure helpers leave the
  running state intact, including when invoked before restoration hooks.
- Exact prompt configuration snippets from `INTEGRATION.md` are exercised by
  the tests, including sourcing twice without duplicate prefixes and preserving
  exit code 7 while returning from a failed command.
- Formatting, Clippy with warnings denied, Zsh syntax checks, and direct release
  and debug builds passed. Both executables report `tcd 0.2.1` and emit the
  current integration sources verbatim. Diff and original-assertion audits passed.

Local platform remains macOS arm64, Nu 0.116.1, Zsh 5.9, Rust 1.98.1 and Python
3.9.6. See [Actions](https://github.com/Belligerently/TempCD/actions) for current
Linux CI results; Windows is unverified. No personal shell configuration was modified.
