# Changelog

Notable changes to skillz. Versions match `plugin.json` and the git tags;
releases before v0.9.0 are described in their commits.

## [Unreleased]

### Changed -- licence

Relicensed from AGPL-3.0-or-later to Apache-2.0 (the owner's decision,
2026-10-10). `plugins/skillz/skills/herdr/SKILL.md`, a modified version of
herdr's agent skill, stays AGPL-3.0-or-later; its text moved to
`LICENSES/AGPL-3.0-or-later.txt`, and the grilling skill's MIT notice is in
`LICENSES/MIT-mattpocock-skills.txt`. 0.10.0 and earlier keep AGPL-3.0-or-later.

## [v0.10.0] -- 2026-10-02

### Added -- herdr-snapshot

A new skill, **herdr-snapshot**: save a herdr session's whole layout together
with the Kommander playbook, task and resumable session id behind each pane, and
recreate that layout elsewhere with `claude --resume <session>` fired into each
pane, for bringing a fleet of agents back after a crash, OOM kill or reboot.

- **Save** matches each tab to its task by title, then by cwd or `.worktree`
  against the locked tasks (anchored, capped when the cwd is too generic), and
  writes one markdown table that the restore step reads back.
- **Restore** relaunches in batches of about six, watches memory pressure and
  swap between batches, answers the two first-run trust dialogs, and never
  resumes a session that is already running.
- **No scripts.** The agent runs the recipe live; an earlier scripted version
  was dropped after review (PR #13).

## [v0.9.0] -- 2026-09-27

### Added -- reflex procedures: Jev decides when, and which

The `reflex` skill has a second engine, **jev**. A standing instruction becomes
a *procedure*: a file in `<config>/procedures/` holding the exact condition
(`covers`, `excludes`), the event kinds it may fire on, and the steps. Nothing of
it sits in the prompt.

- **The hook.** The plugin now ships a hook (`hooks/hooks.json`) on
  `UserPromptSubmit`, `PreToolUse` (Bash, Write, Edit, MultiEdit, NotebookEdit,
  SendMessage) and `Stop`. On each event whose kind some active procedure
  watches, it asks TypeSafe's Jev one Choice question (which procedure applies,
  or none) and, at p >= 0.8, injects that procedure's steps at that moment. A
  matching final reply is sent back once, with the steps, to be fixed before the
  user sees it. About 0.3 s per eligible event; no call when nothing is eligible.
- **Opt-in, fail-open.** Without `<config>/procedures/config.json` the hook exits
  at once, reading and sending nothing. A missing key, an error or a slow answer
  means nothing is injected; a procedure never allows or denies a tool call.
- **Privacy.** The text of eligible events (the user's message, shell commands,
  file writes and edits, outgoing messages, final replies) goes to
  `api.typesafe.ai`, clipped and with credential-looking values redacted, best
  effort. `setup jev` checks the config dir's data rules and asks first.
- **Key by reference.** `TYPESAFE_API_KEY`, or `key_ref` resolved through
  `with-secret`, so the value never passes through argv, output or the log.
- **Evidence.** Every decision goes to `procedures/decisions.jsonl`.
  `dispatch.py` has `test` (dry run), `eval` (events file -> score), `list`,
  `log` and `check`.
- **Tuning before saving.** Adding a procedure drafts must-fire and near-miss
  events and evaluates them against Jev before the file is written.
- **Measured** on the seven procedures in `examples/03-procedure-set`: 30/30 on
  the dev set and 24/24 on a held-out set, median about 330 ms per call
  (jev-1.13). In real Claude Code sessions: `open-pr` fired on the prompt and on
  `gh pr create`, and the agent followed its steps; `report-pr-state` blocked an
  unverified "Head is ..., MERGEABLE" reply once, and the agent read the head back
  and corrected it.

The prompt engine (`REFLEXES.md`) is unchanged, and stays the choice for a config
dir without a key, or for conditions no event carries.

### Added -- the docs standard

`docs/` (tutorials, guides, reference), `examples/` (01-03, each with a README),
`AGENTS.md` with a "Before any release" section, this CHANGELOG, `release.sh`, and
`tests/run-all.sh`. The README is now short (what, why, how, where next); the
per-skill detail moved verbatim to `docs/reference/skills.md`, the layout and
"adding a skill" to their own pages.

### Removed

- The reflex skill's note pointing Kommander users to a Kommander-owned reflex
  skill: Kommander dropped it in its v3.5.0.
