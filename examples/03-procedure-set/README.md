# 03 -- A procedure set, tuned together

**Shows:** seven procedures, drawn from real agent mistakes, that share event
kinds and so compete for the same events. With them, the two event sets they
were measured on:

| Procedure | Fires on | When |
|---|---|---|
| `open-pr` | bash, user_prompt | creating a pull request |
| `release` | bash, user_prompt | creating a version tag or release |
| `report-pr-state` | reply, message | stating a SHA or merge state without having read it back |
| `remote-kill` | bash | `pkill -f` / `killall` over ssh |
| `profile-capture` | bash, write, edit, user_prompt | saving a fact to the pilot profile |
| `secret-needed` | bash, user_prompt | a step needs a credential and isn't using with-secret |
| `gui-step` | bash, user_prompt | a step needs the pilot at a screen |

- `events-dev.json`: 30 events (17 real ones from agent sessions, 13
  near-misses). The procedures' wording was tuned on these.
- `events-heldout.json`: 24 events written afterwards and never tuned on.

**Needs:** python3 and a TypeSafe key (see [02](../02-a-first-procedure/)). The
events' text is sent to TypeSafe.

**Run it**, from the repository root:

```zsh
D=plugins/skillz/skills/reflex/scripts/dispatch.py
export REFLEX_PROCEDURES_DIR=examples/03-procedure-set/procedures
python3 $D eval examples/03-procedure-set/events-dev.json
python3 $D eval examples/03-procedure-set/events-heldout.json
```

**Expected** (measured 2026-09-27, jev-1.13): `30/30` and `24/24`, median about
330 ms per call. Events whose kind no procedure watches make no call (0 ms).

What the tuning taught, and what `excludes` is for:

- Jev reads literally. With `git tag` in `release`'s condition, `git tag -l` (just
  listing) matched, until `excludes` said listing tags does not count.
- Known rules stay in code: `report-pr-state` fires only on `reply` and
  `message`, so reading the head back with `gh pr view` is never mistaken for
  reporting it.

Measured, not guaranteed: the procedures and both sets were written by the same
author, and the held-out set was drafted after a few `covers` lines had been
widened. Replay your own sessions' events before trusting a threshold.
