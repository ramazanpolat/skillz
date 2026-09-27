# 02 -- Your first procedure

A standing rule that fires on its own: "whenever I open a pull request, request a
Codex review once and read the head back before reporting it". About ten
minutes. You need skillz installed ([01](01-install-and-first-skill.md)),
python3, and a TypeSafe API key (https://console.typesafe.ai/), stored where
`with-secret` can lend it, or exported as `TYPESAFE_API_KEY` in the shell that
starts Claude Code.

What leaves your machine: once set up, the text of every event a procedure is
eligible for (here: your messages and the shell commands Claude runs) is sent to
TypeSafe's API, clipped and with credential-looking values redacted. Skip this
tutorial if your data rules forbid that.

## 1. Set up the jev engine

```text
/skillz:reflex setup jev
```

Claude checks your config's data rules, says what will be sent, asks where the
key is stored (the reference, never the value), writes
`<config>/procedures/config.json` and runs a check. The last line of the check
reads `live call: ok, <n> ms`.

## 2. Add the procedure

```text
from now on, whenever I'm about to open a PR: request @codex review once in
the body, and before telling me the head, read it back with gh pr view
```

Claude drafts `open-pr.md`. It then shows six test events (three that must fire,
three that must not) and Jev's decision on each. If one is wrong, it sharpens
the `covers` / `excludes` lines and runs them again. Say yes, and it writes
`procedures/open-pr.md` and `procedures/evals/open-pr.json`.

## 3. Watch it fire

Open a PR in any repository the way you normally would ("open a PR for this
branch"). Before `gh pr create` runs, the hook asks Jev; the procedure's steps
reach Claude, and its reply starts with:

```text
[procedure: open-pr] firing: opening a PR for the current branch
```

The PR body carries `@codex review`, and the head is reported "as read back".

## 4. Read the evidence

```zsh
C="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
D="$(jq -r '.plugins["skillz@skillz"][0].installPath' "$C/plugins/installed_plugins.json")/skills/reflex/scripts/dispatch.py"
python3 "$D" log 5
```

Each line is one decision: the event kind, Jev's choice and probability, what the
hook did, and the latency. A shell command like `ls` shows `none`; your PR shows
`fire`.

## What you did

- Opted a config dir in to the jev engine.
- Wrote a procedure as a sentence, and saw it tuned against Jev before it was saved.
- Saw it fire at the moment that mattered, with nothing in the prompt beforehand.

More: [the procedures guide](../guides/reflex-procedures.md) (test, pause,
migrate, troubleshoot), and [examples/03](../../examples/03-procedure-set/) (a
tuned set of seven).
