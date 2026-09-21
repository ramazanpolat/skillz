---
name: herdr-snapshot
description: "Save a herdr session's full workspace/tab/pane layout together with which Kommander playbook + task + resumable session id each pane was running, and later recreate that exact layout in a new or different herdr session with the right `claude --resume <session>` fired into each pane. Use after a host crash, OOM kill, reboot, or `herdr server stop` wiped every agent process but left the herdr layout (or a saved snapshot) intact and the pilot wants their tabs and agents back — \"resurrect my sessions\", \"bring back my agents\", \"the machine rebooted and killed everything\", \"recreate this herdr layout in a new session\", \"save/back up my herdr layout\". Also use proactively to snapshot a layout before a risky reboot/update, or just to back up a fleet of long-running Kommander sessions periodically. Requires the herdr skill and a local Kommander playbook install (or several) under ~/.claude-playbooks/."
---

# herdr-snapshot — save and resurrect a herdr layout full of Kommander agents

Pairs [herdr](../herdr/SKILL.md) (workspaces/tabs/panes) with the
[Kommander playbook](https://github.com/ramazanpolat/kommander-playbook)'s task-lock
system (`~/.claude-playbooks/*/data/tasks/*/.lock.held`) to answer a question herdr
alone can't: *which Kommander task, in which playbook, was each pane actually
running* — and to recreate that exact fleet of agents somewhere else.

The core trick: a Kommander pilot's habit is to **title each tab after the task its
agent is working** (`kommander-helper`/the SessionStart flow makes this natural).
A task's lock is **session-keyed**, so once you know which task a tab held, its
`.lock.held` file's `session=` id is exactly the argument `claude --resume` needs
to restore that pane's *exact prior conversation* — not a fresh session, the real
one, picking up mid-thought. This skill automates the whole chain: capture the
layout → match every tab to a task → recover the session id → recreate the layout
elsewhere → fire the resumes in safe batches.

Two scripts, no non-stdlib Python dependencies:

- `scripts/snapshot.py` — **read-only.** Captures a herdr session's layout and
  matches every tab.
- `scripts/resurrect.py` — recreates the layout in a target session, then batch-
  relaunches it.

## When to reach for this

- The host crashed, OOM-killed, or rebooted and every Kommander/Claude Code
  process died, but herdr itself (or the session it was running) still has the
  workspace/tab layout — or you have an earlier `snapshot.py` capture on disk.
- The pilot wants a fresh herdr session (`herdr --session <name>`) populated with
  the same tabs and the same agents resumed, so they can review before diving
  back in — this is the common case: build the layout, review, *then* relaunch.
- Periodic backup: run `snapshot.py save` on a schedule so a crash never loses
  the map of what was running where.

## Quickstart

```bash
# 1. Read-only: capture + match. Point --session at the session that still has
#    the layout (often "default" if the pilot's regular session survived a
#    process-only crash) or the one you're in right now if $HERDR_SOCKET_PATH
#    is already set.
scripts/snapshot.py save --session default --out ~/.herdr-snapshots/pre-reboot
#   -> writes pre-reboot.json (feeds resurrect.py) and pre-reboot.md (read this)

# 2. Show the pilot the .md report and get their read before touching anything.
#    It groups tabs by workspace, one row per tab: decision / playbook / task /
#    session / why. See "Reading the report" below for what to do with each
#    decision and which ones need a second look.

# 3. Recreate the layout in a new or existing herdr session (mechanical, safe --
#    just creates empty panes with the right labels/cwd, launches nothing):
scripts/resurrect.py layout --snapshot ~/.herdr-snapshots/pre-reboot.json \
  --target-session recovery
#   -> writes pre-reboot.instantiated.json (same rows + new pane ids)

# 4. See the relaunch plan before firing anything:
scripts/resurrect.py relaunch --snapshot ~/.herdr-snapshots/pre-reboot.instantiated.json \
  --target-session recovery --dry-run

# 5. Actually relaunch, in small batches, watching real memory health between
#    each one:
scripts/resurrect.py relaunch --snapshot ~/.herdr-snapshots/pre-reboot.instantiated.json \
  --target-session recovery
```

`resurrect.py all` runs steps 3+5 back to back if you're confident and don't need
to review the plan in between — but for anything beyond a handful of tabs, do the
phases separately and read the report first. That review step is where a pilot
catches what the matcher can't (see below).

## Reading the report — what each decision means and what to do with it

| Decision | Meaning | What to do |
|---|---|---|
| `resume` | Tab title matched a task by name, and that task's lock still carries a `session=` id — `claude --resume <session>` recovers the *exact* prior conversation. | Default: let `relaunch` fire it. Spot-check a few, especially ones whose note says `cwd-matched` rather than a name match (see Gotchas). |
| `fresh` | Task identified by name, but it isn't currently locked (parked cleanly, or never opened this session). No conversation to resume. | `relaunch --include-fresh` launches the bare playbook and picks the task from its menu — two-step, slightly slower, off by default. |
| `uncertain` | Real candidates exist but the matcher won't guess — either two locked tasks tied on recency, or the only cwd-matched candidates showed up after the tab's exact-name match turned out to be a completed task. Each candidate's Goal text is included. | Never auto-launched. Read the candidates, pick one (or none), and if there's still no good answer, **read every currently-locked task's `TASK.md` Goal by hand and check for thematic/topical relevance, not just path strings** — this is exactly how a tab named after a skill (not a task) got matched to the right dormant session once; substring cwd-matching can't do that kind of reasoning. |
| `plain` | No task name or cwd evidence found at all. | Usually correct (a non-Kommander shell, a database client, a plain dev tab). But see Gotchas — this is also where a real match can hide when its TASK.md never once writes the repo's literal path. If the pilot says "I'm pretty sure an agent was working there," re-investigate that one tab by hand: list every currently-*locked* task across every playbook (`.lock.held` present), sorted by lock recency, and read Goals for relevance to that tab's cwd/repo — not just a string match. |
| `duplicate` | The tab-matching found the *same* session id already claimed by an earlier tab in the same layout. | Correctly left un-launched — never fire the same `--resume <session>` into two panes at once. |

## Gotchas (all found by actually running this against a real 70-tab, 17-workspace
crash recovery)

- **Raw "free pages" is not a memory-health signal on macOS.** It's near-zero on
  any healthy system because macOS aggressively uses free RAM as disk cache.
  `resurrect.py` checks `memory_pressure`'s **free percentage** and
  `vm.swapusage`'s **used** value instead — swap actually being used, or free%
  dropping hard, is the real signal. Don't "fix" the batching logic to watch raw
  free pages; it will cry wolf constantly.
- **Post-reboot PID reuse produces false "still alive" reads.** After a reboot,
  PIDs restart from low numbers, so an old lock's recorded pid can coincidentally
  belong to an unrelated process (`WiFiAgent`, an XPC service — genuinely happened
  during development). `resurrect.py`'s alive-check confirms the pid is *also*
  a `claude` process, not just alive. If you write ad hoc liveness checks, do the
  same — a bare `kill -0 $pid` is not enough.
- **Two Claude Code first-run dialogs default to declining, and will sit a pane
  stuck forever if nothing answers them:** the workspace-trust prompt (new cwd
  for that playbook) and the external-imports prompt (a skill's `@import` from
  outside the project, e.g. browser-harness). Both show `❯ No, ...` as the
  pre-selected option. `relaunch` sweeps every launched pane's `agent_status` for
  `blocked` afterwards and sends Down+Enter to select "Yes" — recognized by the
  visible text containing "trust this folder" / "external imports". A dialog it
  doesn't recognize is left alone and reported, on purpose.
- **cwd-only matches (no tab-title match at all) are the weakest signal the
  matcher has**, and it will confidently pick one if there's exactly one
  candidate. This is right most of the time (an untitled tab in a
  single-purpose repo) but it *will* pick a plausible-looking wrong answer when
  several loosely-related historical tasks share one repo and the tab is titled
  with something generic (a bare person's name, a one-word nickname) — this
  happened for real with test-persona-named tabs (`mira`, `deniz`) in a shared
  repo, matching them to unrelated tasks that merely lived in the same directory.
  Eyeball every `resume` row whose note starts with "no name match, cwd-matched"
  before relaunching a batch you haven't reviewed.
- **A task named for its content, not its repo, is invisible to cwd matching.**
  A task whose `TASK.md` discusses "the README" or "the release" without ever
  writing the literal path won't be found by substring search even though it's
  exactly the right task — this is why `uncertain` exists for the
  exact-name-match-but-DONE case instead of silently guessing. When this
  happens, the fix is reading, not more regex: list every currently-locked task,
  sorted by `.lock.held`'s `at=` (most recent first), and check Goals for topical
  relevance to the tab.
- **A lock's `session=` id, not the pid, is what makes a task resumable.**
  Kommander locks are session-keyed specifically so `claude --resume` survives a
  quit/crash; the pid in `.lock.held` is only for liveness checks. Don't try to
  "resume" via pid.
- **Batch size matters less than watching between batches.** 47 concurrent
  `claude --resume` processes did not come close to real memory pressure on a
  24GB Mac (swap stayed at 0 throughout) — Chrome, not a fleet of resumed Claude
  Code sessions, is usually the actual RAM hog. Don't assume you need tiny
  batches; do keep checking real health between them, since the *next* fleet
  might be bigger or the host might be smaller.
- **`herdr session list` is how you find a target/source session's socket** —
  both scripts resolve `--session`/`--target-session` names through it. A
  session must already exist (`herdr --session <name>` once, interactively, to
  create it) before either script can target it.

## Design notes

- `snapshot.py` never mutates anything — no lock acquire/release, no herdr writes
  beyond `session list` / `api snapshot`. Safe to run against a live, healthy
  session just to back it up.
- The matcher works across **every** local playbook install under
  `~/.claude-playbooks/`, not just one — a tab can resolve to any playbook's
  task, which is normal (a pilot commonly runs several playbook installs from
  one herdr session, one per client/project).
- Playbook → launcher command is read from each install's `.playbook` manifest
  (`alias = "..."`), not by parsing `claude-playbook list`'s text table — more
  robust to output-format changes.
- `resurrect.py relaunch` never touches a `duplicate`, `uncertain`, or (without
  `--include-fresh`) `fresh` row. Those need a human call; the report lists them.
- Everything is stdlib Python 3 + the `herdr` CLI + macOS `memory_pressure`/
  `sysctl`/`ps`. No pip installs.
