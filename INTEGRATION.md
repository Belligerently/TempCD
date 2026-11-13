# Diagnostics, structured status, and prompts — v0.2.1

Load the shell integration first. None of these features needs Python, a
daemon, or external JSON tools at runtime. Existing `tcd directory` behavior
is unchanged; the prompt indicator is disabled until you opt in.

## Diagnose setup

```sh
tcd --doctor
```

Returns success when the expected callbacks are registered exactly once,
their functions exist, and the integration version/session markers match.
Missing or duplicated callbacks and mismatched markers return nonzero with
instructions to reload after hook setup or restart after a version change.
An entered doctor command leaves a pending visit intact even on failure.

This checks the standard registration, not arbitrary third-party callback
behavior. Other hooks can still abort execution, change cwd, or replace
callbacks later. The version check concerns loaded integration markers; it
does not run or verify an external binary on PATH. During upgrades, check
`^tcd --version` in Nu or `command tcd --version` in Zsh separately.

## Read structured status

```sh
tcd --status --json
```

Both shells emit the same JSON schema, for example:

```json
{"schema_version":1,"version":"0.2.1","shell":"nu","active":false,"return_to":null,"depth":0}
```

| Field | Meaning |
| --- | --- |
| `schema_version` | `1`; the data format version |
| `version` | Loaded integration version |
| `shell` | `nu` or `zsh` |
| `active` | Whether a pending visit matches the current directory |
| `return_to` | Next return destination, or `null` when inactive |
| `depth` | Pending nesting depth, or `0` when inactive |

Paths are JSON-escaped, including quotes, backslashes, and control characters.
Consumers should check the schema version and tolerate additional fields.
Like human-readable status, this control command does not consume the visit.
`--json` is supported only together with `--status`.

For prompt/environment hooks, use the **read-only helpers**:

- `tcd-status`: a native record in Nu; the same JSON object in Zsh.
- `tcd-prompt`: prompt-ready text such as `[return: /original/directory] `,
  or an empty string when inactive. ASCII control characters are replaced
  with `?`; Zsh prompt escapes are quoted. Use structured status for raw paths.

These helpers never reset pending execution or change directories. If you
type a helper as the next ordinary command, the normal execution hook still
consumes that submitted line. Inside a prompt hook, they simply observe state.
Continue to use `tcd --status` for interactive inspection; do not call the
stateful `tcd` controls from prompt/environment hooks.

## Optional prompt indicator

Put the relevant snippet after integration and theme setup. Both preserve
the existing prompt, leave the right prompt alone, and guard against duplicate
prefixes when configuration is sourced again.

### Nushell

Add to `config.nu` after your prompt is configured:

```nu
if $env.__TCD_PROMPT_OWNER? != $nu.pid {
    let previous_prompt = $env.PROMPT_COMMAND
    $env.PROMPT_COMMAND = {||
        let original = if ($previous_prompt | describe) == 'closure' {
            do $previous_prompt
        } else { $previous_prompt }
        $"(tcd-prompt)($original)"
    }
    $env.__TCD_PROMPT_OWNER = $nu.pid
}
```

### Zsh

Add to `.zshrc` after your theme is configured. `PROMPT_SUBST` enables the
read-only helper substitution:

```zsh
setopt PROMPT_SUBST
if [[ $PROMPT != *'$(tcd-prompt)'* ]]; then
    PROMPT='$(tcd-prompt)'"$PROMPT"
fi
```

The destination is treated as literal display text: `%` prompt sequences and
command-like text in a directory name do not execute or expand as prompt code.
For themes that regenerate `PROMPT` on every cycle, insert `tcd-prompt` through
the theme's own customization mechanism instead of wrapping a transient value.

To disable the indicator, remove the optional snippet and open a new shell.
Do not remove TempCD's integration or callbacks unless you are uninstalling it.
