# v0.2.1 review and next steps

Review for v0.2.1, based on v0.2.0. Scope: the Rust CLI, Nu/Zsh integration, temporary
test generation, configuration instructions, and CI workflow.

## Confirmed bugs fixed

| Finding | Before | Current behavior | Verification |
| --- | --- | --- | --- |
| Nu comment-only input consumed a visit | `tcd project`, then `# a note`, returned immediately | Whitespace/comment-only lines leave the visit pending until executable input | Regression cases for comments and leading whitespace; both shells, with Zsh interactive comments enabled |
| Non-UTF-8 executable argument panicked | An invalid Unix byte argument caused Rust to panic with exit 101 | Invalid Unicode arguments produce a usage error on stderr and exit 2 | Actual executable process test; no panic, no stdout |

Additional process checks verify that direct executable directory arguments
report the integration/setup error with exit 2, and a closed stdout pipe is
handled successfully without a panic or error message.

## Confirmed boundaries

- **Syntax errors differ by shell.** Nu's pre-execution hook runs before
  parsing, so invalid input consumes a visit. Zsh's hook runs after parsing,
  so invalid syntax leaves the visit pending. Tests check the next command's
  actual directory as well as the prompt after the error. This is documented
  behavior; no line-editor bindings or traps were added to alter Zsh parsing.
- **Hook ownership matters.** Replacing hook lists or aborting the shell's
  callback cycle can disable restoration. Explicit directory changes cancel
  the pending stack. Calling `tcd` controls from prompt/environment hooks is unsupported; use the
  read-only `tcd-status` and `tcd-prompt` helpers there.
- **Deleted/renamed current directories require shell recovery.** Nu may stop
  running hooks while its current path is invalid. Ordinary `cd` to an existing
  path repairs that state; TempCD cannot guarantee restoration beforehand.
- **Commands are submitted lines.** Pipelines and compound commands run as one
  visit; background jobs consume the line when launched. Shell termination
  prevents any subsequent return. Status controls should be standalone lines.
- **Platform evidence is limited.** Current review tests were run on macOS
  with Nu 0.116.1 and Zsh 5.9. Historical Linux CI passed the prior version.
  See [Actions](https://github.com/Belligerently/TempCD/actions) for current Linux
  CI results. Windows is unverified.

## Implemented in v0.2.1 and remaining proposals

1. **Implemented: `tcd --doctor`.** Checks standard callback registration,
   duplicate/missing callbacks, function presence, and integration session/version
   markers. It keeps visits pending; arbitrary hook behavior and the executable
   on PATH remain outside its scope.
2. **Implemented: structured status.** `tcd --status --json` shares schema 1
   across shells. The `tcd-status` helper observes state without holding visits
   or changing cwd when used by a prompt/environment hook.
3. **Implemented: optional prompt indicator.** `tcd-prompt` returns sanitized,
   prompt-ready destination text. Opt-in configuration preserves existing prompts;
   callbacks do not enable or replace a user's prompt automatically.
4. **Zsh help and completion:** add consistent help text, control-flag
   completion, and destination completion. Nu already provides path-typed
   argument completion.
5. **Release downloads and broader CI:** publish executable archives with
   checksums, test supported Nu versions on Linux and macOS, and assess Windows
   separately before claiming shell support there.

Items 4–5 remain proposals. Configuration, the JSON schema, and diagnostic
boundaries are documented in [INTEGRATION.md](INTEGRATION.md). All three
implemented features have regression coverage, including literal path display,
JSON escaping, nested visits, read-only hooks, and diagnostic failures. Python
remains development-only test tooling, and Cargo handles builds directly.
