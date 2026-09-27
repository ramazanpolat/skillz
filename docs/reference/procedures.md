# Reference: reflex procedures (the jev engine)

The exact behaviour of the `reflex` skill's jev engine: files, fields, hook
events, thresholds, output, log and environment. How-to steps are in
[the procedures guide](../guides/reflex-procedures.md).

## Files

```
<config>/procedures/            <config> = $CLAUDE_CONFIG_DIR, else ~/.claude
    config.json                 opt-in switch and settings; without it the hook does nothing
    <name>.md                   one procedure per file
    evals/<name>.json           optional: the events a procedure was tuned on
    decisions.jsonl             every decision the hook made (local only)
    .state/<session>.json       per-session memory (first fire, reply blocks); pruned after 7 days
```

Files starting with `.` or `_`, and `README.md`, are not procedures.

## config.json

| Key | Default | Meaning |
|---|---|---|
| `engine` | `"jev"` | anything else turns the hook off |
| `model` | `"jev-latest"` | the TypeSafe model |
| `fire` | `0.8` | at or above: inject the steps (on a reply: block it once) |
| `hint` | `0.5` | at or above, below `fire`: a one-line hint |
| `timeout_s` | `2.5` | the Jev call's timeout; on expiry nothing is injected |
| `key_ref` | none | a with-secret reference (`keychain:typesafe`) used when `TYPESAFE_API_KEY` is not in the environment |
| `log` | `true` | write `decisions.jsonl` |
| `api_url` | `https://api.typesafe.ai/v1/systemone` | the endpoint |

## Procedure file

```markdown
---
name: <name>                    must equal the file name; lowercase-with-dashes; not "none"
title: <one line>               optional
mode: auto | ask                default ask
status: active | paused         default active
fires_on: [<kind>, ...]         required
covers: <the exact condition>   required; one line
excludes: <near-misses>         optional; one line
---
<the steps>                     required; shown to the agent when it fires
```

One `key: value` per line; a list as `[a, b]`; values may be quoted; no
multi-line values. A file that fails to parse is skipped and listed as
`BROKEN` by `dispatch.py list`; the others keep working.

## Kinds and hook events

| Kind | Hook event | The text Jev sees |
|---|---|---|
| `user_prompt` | `UserPromptSubmit` | the user's message |
| `bash` | `PreToolUse`, tool `Bash` | the command |
| `write` | `PreToolUse`, tool `Write` | `file: <path>` and the new content |
| `edit` | `PreToolUse`, tools `Edit`, `MultiEdit`, `NotebookEdit` | `file: <path>` and the new text |
| `message` | `PreToolUse`, tool `SendMessage` | `to: <recipient>` and the message |
| `reply` | `Stop` | the final reply (`last_assistant_message`, else the transcript's last assistant text) |

Other tools never reach the dispatcher. Text longer than 4000 characters is
clipped to its first and last 2000. Before sending, values that look like
credentials are replaced with `<redacted>`: `Bearer <token>`,
`password` / `passwd` / `pwd` / `token` / `secret` / `api_key` / `authorization`
values after `=` (to the next space) or `:` (to the end of the line), quoted
or bare or as a JSON value; `--password` / `--token` / `--secret` / `--api-key`
flag values; the password in `scheme://user:password@host`; and
`sk-...`, `ghp_...`, `xox?-...`, `AKIA...` strings. This is best effort, not a
guarantee: do not put secret values in commands at all.

## One decision

1. The eligible procedures: `status: active` and the event's kind in `fires_on`.
   None -> exit, no call.
2. One Choice question to Jev: state `{event: <kind description>, content: <text>}`;
   the options are the eligible procedures (`{covers, excludes}`) plus `none`.
3. `p` = the probability of the chosen option.
   - `none`, or `p < hint`: nothing.
   - `hint <= p < fire`: a hint (never on `reply`).
   - `p >= fire`: fire.

## What the agent receives

| Situation | Output |
|---|---|
| fire, first time in the session | `hookSpecificOutput.additionalContext`: `[procedure: <name>] Jev matched this moment (...; p=0.97)`, the mode rule, the disclosure rule, the read-only rule, the title and the steps |
| fire again in the same session | a one-line `applies again` reminder with the file path |
| hint | `[procedure: <name>] may apply ...`, its `covers`, and the file path |
| fire on `reply` | `{"decision": "block", "reason": <the steps>}`, at most once per procedure per turn (the next user message resets it), never while `stop_hook_active` |

No `permissionDecision` is ever set: a procedure never allows or denies a tool
call. Exit status is always 0.

## decisions.jsonl

One JSON object per decision:

| Field | Meaning |
|---|---|
| `ts` | local time, ISO 8601 |
| `session` | the Claude Code session id |
| `kind` | the event kind |
| `eligible` | the procedures offered to Jev |
| `choice`, `p` | Jev's answer |
| `action` | `fire`, `hint`, `block`, `none` or `error` |
| `ms` | the Jev call's latency |
| `sha` | the first 16 hex of the sent text's SHA-256 |
| `preview` | the first 120 characters of the sent (redacted) text |
| `error` | on `error`: the exception |

## The key

1. `TYPESAFE_API_KEY` in the environment.
2. Else `key_ref` with `with-secret` on `PATH`: the dispatcher runs itself again
   as `with-secret TYPESAFE_API_KEY=<key_ref> -- python3 dispatch.py ...`. The
   value never appears in argv, output or the log.
3. Else nothing happens (no call, no output).

## CLI

`python3 <skill>/scripts/dispatch.py <mode>`:

| Mode | Does |
|---|---|
| `hook` | the hook entry: an event on stdin |
| `test <kind> "<text>"` | a dry run: the decision, nothing injected, logged or remembered |
| `eval <events.json>` | `[[kind, text, expected], ...]`: each result, the score, the median latency; exit 1 unless all match |
| `list` | procedures: status, mode, fires from the log, kinds; broken files |
| `log [N]` | the last N decisions (default 20) |
| `check` | config, procedures, key, one live call |

## Environment

| Variable | Used for |
|---|---|
| `CLAUDE_CONFIG_DIR` | where `procedures/` is (default `~/.claude`) |
| `TYPESAFE_API_KEY` | the key |
| `REFLEX_PROCEDURES_DIR` | override the procedures directory (tests, evals, a scratch draft) |
| `REFLEX_JEV_URL` | override the endpoint (the unit tests' mock) |
