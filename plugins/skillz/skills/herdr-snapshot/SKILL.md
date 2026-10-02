---
name: herdr-snapshot
description: "Save a herdr session's full workspace/tab/pane layout together with which Kommander playbook + task + resumable session id each pane was running, and later recreate that exact layout in a new or different herdr session with the right `claude --resume <session>` fired into each pane. Use after a host crash, OOM kill, reboot, or `herdr server stop` wiped every agent process but left the herdr layout (or a saved snapshot .md) intact and the pilot wants their tabs and agents back — \"resurrect my sessions\", \"bring back my agents\", \"the machine rebooted and killed everything\", \"recreate this herdr layout in a new session\", \"save/back up my herdr layout\". Also use proactively to snapshot a layout before a risky reboot/update, or just to back up a fleet of long-running Kommander sessions periodically. Requires the herdr skill and a local Kommander playbook install (or several) under ~/.claude-playbooks/."
---

# herdr-snapshot — save and resurrect a herdr layout full of Kommander agents

Pairs [herdr](../herdr/SKILL.md) (workspaces/tabs/panes) with the
[Kommander playbook](https://github.com/ramazanpolat/kommander-playbook)'s
task-lock system (`~/.claude-playbooks/*/data/tasks/*/.lock.held`) to answer a
question herdr alone can't: *which Kommander task, in which playbook, was each
pane actually running* — and to recreate that exact fleet of agents somewhere
else.

The core trick: a Kommander pilot's habit is to **title each tab after the task
its agent is working**. A task's lock is **session-keyed**, so once you know
which task a tab held, its `.lock.held` file's `session=` id is exactly the
argument `claude --resume` needs to restore that pane's *exact prior
conversation* — not a fresh one, the real one, picking up mid-thought.

**No scripts ship with this skill.** When you run it, you — the agent — read
this recipe and execute the actual `herdr` / shell commands yourself, live,
adapting to what you actually see. That's deliberate, not an oversight: an
earlier version of this skill packaged the matching and restore logic as
Python scripts, and review turned up a run of bugs that all trace back to the
same root cause — code that hardcodes assumptions and can't react to what's
actually in front of it. A `herdr` subcommand name had drifted from what the
installed CLI accepts (`herdr wait output` doesn't exist; the real command is
`herdr pane wait-output`, found only by actually running `herdr pane --help`
against a live install, not by trusting written docs — this file included).
A batch loop silently disabled its own memory-safety check on any unexpected
error instead of failing loudly. Doing this live closes that whole class of
failure: **before trusting any `herdr` subcommand name in this file, verify it
against `herdr --help` / `herdr <group> --help` first** — treat every command
shown below as "this is what it was when this was written," not gospel.

## Part 1 — save a snapshot

Goal: one markdown file, capturing every workspace/tab/pane in a herdr session
plus, for every tab, which Kommander playbook + task + resumable session id it
was probably running.

### 1. Capture the raw layout

```bash
herdr session list                      # find the socket for the session you want (e.g. "default")
HERDR_SOCKET_PATH=<socket-from-above> herdr api snapshot > /tmp/raw-snapshot.json
```

Pull `result.snapshot.workspaces`, `.tabs`, `.panes` (each pane has `cwd`) out
of the response.

### 2. Build the task index

Every local Kommander playbook install lives at `~/.claude-playbooks/<name>/`,
tasks under `data/tasks/<task-folder>/`. For each install:

- Read `<install>/.playbook` for the `alias = "..."` line — that's the
  launcher command (e.g. `kommander-9router`'s alias is `k9`, not its
  directory name). No `.playbook` file: fall back to the directory name.
- List `data/tasks/*` (skip dotfiles). A `DONE--`-prefixed folder is a
  completed task; strip the prefix to get its bare name.
- If `.lock.held` exists, it's one line: `acquired: pid=<pid> host=<host>
  session=<id> at=<timestamp>`. Parse `session=` and `at=`.

This is a lot of small files across possibly a dozen playbooks and hundreds of
tasks — don't spend one Read-tool-call per file. Shell out for the bulk scan:

```bash
for f in ~/.claude-playbooks/*/data/tasks/*/.lock.held; do
  echo "== $f =="; cat "$f"
done
```

A short inline `python3 -c "..."` heredoc in the Bash tool is a good way to
turn that into something you can actually reason about (token-set matching,
sorting by recency) — a one-off snippet you run and discard, not a file you
commit. That's the same technique this skill itself was originally built with.

### 3. Match every tab to a task

For each tab, try in order, stopping at the first that yields something:

1. **Exact name match** — normalize the tab label and every task name
   (lowercase, split on non-alphanumerics into a token set) and compare for
   equality.
2. **Fuzzy name match** — Jaccard similarity (`|intersection| / |union|`) of
   the same token sets, threshold ~0.3. `k-search` vs. a task named
   `kommander-search` scores 1/3 ≈ 0.33 — intentionally loose, since tab
   titles get abbreviated.
3. **cwd fallback** — when there's no name match, or the only name match is a
   `DONE--` task (a tab can get repurposed after its original task finished —
   seen for real: a tab titled after a repo matched only a finished task by
   that repo's name, but the actual live task was named after its *content*,
   an unrelated README rewrite), search every **currently-locked**,
   **not-already-claimed-by-another-tab** task's `TASK.md` and `.worktree` for
   the pane's cwd — check both the absolute path and its `~`-shorthand form
   (`TASK.md` prose often writes `~/foo`, not the expanded path). An exact
   `.worktree` match is stronger evidence than a `TASK.md` substring mention.
   - **Cap it**: more than ~6 cwd matches means the cwd itself is too generic
     (bare `$HOME`, a shallow parent like `~/DEV`) to mean anything — treat it
     as no match rather than picking one. A bare-`$HOME` tab in real testing
     "matched" 32 unrelated tasks; none of them meant anything.
   - **Anchor the match**: cwd `/Users/x/dev/api` is a substring of
     `/Users/x/dev/api-gateway` — require an exact path or a `/`-bounded
     prefix, not a raw substring.
   - **Reserve** any task that's already the exact-name match for some *other*
     tab in this same snapshot — don't let a cwd search poach a task that
     clearly belongs to a different, exactly-titled tab.
4. A locked candidate with a `session=` id → that tab **resumes**. Two locked
   candidates tied (the same task name exists, separately locked, under two
   different playbook installs — happens when a pilot runs related work under
   more than one install over time): prefer the more recent `.lock.held`
   `at=` — it always reflects the *last* acquire, and a clean quit leaves the
   marker in place rather than deleting it, so recency is a genuine "was this
   the one still open" signal. Genuinely tied (can't tell): don't guess — mark
   it **uncertain**, list both candidates with their `TASK.md` Goal text, and
   let the pilot (or your own closer reading) decide.
5. Task exists but isn't locked → **fresh**: no conversation to resume;
   restoring this tab means launching the playbook and picking the task from
   its own menu, not `--resume`.
6. Nothing found → **plain**: not a Kommander tab (untitled herdr default
   numbering, a database client, a repo being browsed plainly). If the pilot
   says they're sure an agent was working in a tab you called plain,
   re-investigate that *one* tab specifically: list every currently-locked
   task system-wide sorted by `at=` descending, and read Goals for topical
   relevance to that tab's cwd — not just a string match. This is exactly how
   a task named for its content, not its repo, got found once; no
   cwd-substring search will ever catch that case on its own.
7. The same `session=` id assigned to two tabs → the second is a
   **duplicate**. Never resume the same session into two panes.

### 4. Write the markdown

One file, grouped by workspace, one row per tab: label, cwd, decision,
playbook/launcher, task, session id (short form is fine), and the reasoning in
one sentence. Save wherever the pilot wants (default suggestion:
`~/.herdr-snapshots/<session>-<timestamp>.md`). **This file is the snapshot**
— restoring re-reads this same table, so keep it a real, consistently-ordered
markdown table even though a human reads it first. No JSON sidecar, no second
format to keep in sync — if you need structure while restoring, re-parse this
table when you get there.

## Part 2 — restore a snapshot into a (new or existing) herdr session

### 1. Recreate the layout

Read the snapshot markdown. For each workspace, in tab order:

```bash
herdr session list   # resolve --target-session's socket first
HERDR_SOCKET_PATH=<target-socket> herdr workspace create \
  --cwd <first-tab-cwd> --label <ws-label> --no-focus
# parse result.workspace.workspace_id / result.tab.tab_id / result.root_pane.pane_id
HERDR_SOCKET_PATH=<target-socket> herdr tab rename <that-tab-id> "<first-tab-label>"
```

`workspace create --label` names the *workspace* (and its root tab defaults to
a number) — the rename fixes the root tab's own label when it differs from
the workspace label, which it usually does. For every other tab in that
workspace:

```bash
HERDR_SOCKET_PATH=<target-socket> herdr tab create \
  --workspace <ws-id> --cwd <cwd> --label "<label>" --no-focus
```

again parsing the new `tab_id` / `root_pane.pane_id` from the result. Keep a
running note of `tab label -> new pane id` in your own working context (or a
scratch file) — you need it for step 2.

### 2. Relaunch, in small batches, watching real memory health

Before firing any `--resume` for a `resume`-decision row, skip it if:

- its session id is already running somewhere:
  `ps -Ao args | grep -- '--resume <session>'`, **or**
- its `.lock.held` pid is alive **and** is actually a claude process — check
  `ps -p <pid> -o command=` for the executable ending in `/claude` or equal to
  `claude`, don't substring-match `/claude` against the *whole* command line
  (that also matches unrelated paths like `~/claude-notes/...`). A bare
  `kill -0 <pid>` isn't enough either: after a reboot, PIDs restart low and
  can coincidentally land on a totally unrelated process — this happened for
  real, an old lock's recorded pid landed on `WiFiAgent` after one reboot.

Fire ~6 panes at a time:

```bash
herdr pane run <new_pane> "<launcher> --resume <session>"
```

After each batch, pause a few seconds and check *real* health — not raw free
page count, which sits near zero on any healthy macOS system and means
nothing (macOS uses "free" RAM as disk cache by design):

```bash
memory_pressure | grep -E "free percentage|Swapins|Swapouts"
sysctl vm.swapusage
```

Stop launching further batches and report to the pilot instead of guessing if
swap `used` is above 0, or if free% is dropping hard batch over batch. There's
no universal safe threshold — 47 concurrent `claude --resume` processes cost
one real 24GB Mac about 30 points of free% and never touched swap; watch the
trend, don't hardcode one number.

`fresh` tabs (no session to resume) need a different two-step, and are
optional — ask the pilot before launching any, since a fresh start doesn't
recover a conversation, it just opens the task from scratch:

```bash
herdr pane run <pane> "<launcher>"
herdr pane wait-output <pane> --match "Type the task name" --timeout 20000   # verify this subcommand name first, see the intro
herdr pane run <pane> "<task-name>"
```

Never auto-launch an `uncertain` or `duplicate` row.

### 3. Sweep for stuck panes

Two Claude Code first-run dialogs default to declining and leave a pane stuck
forever if nothing answers them: **workspace trust** (a new cwd for that
playbook) and **external-imports trust** (a skill's `@import` reaching outside
the project — browser-harness is a common one). Both pre-select `❯ No, ...`.
After each batch, check every pane you just launched:

```bash
herdr pane read <pane> --source visible --lines 20
```

If the text contains "trust this folder" or "external imports"
(case-insensitive), select "Yes":

```bash
herdr pane send-keys <pane> Down
herdr pane send-keys <pane> Enter
```

Re-read the pane afterward — some panes stack a second dialog right after the
first (workspace trust, then external-imports trust). Don't blindly answer
text you don't recognize as one of these two specific patterns; report it to
the pilot instead of guessing.

## Design notes

- No scripts ship with this skill, on purpose (see the intro) — everything
  above is something you run live, adapted to what you actually observe.
- Prefer shelling out (loops, `grep`, short one-off `python3 -c` snippets)
  over one Read-tool-call per file when scanning dozens of playbooks' task
  folders. This is bulk, repetitive file I/O, not something worth burning
  individual tool-call turns on.
- Works across **every** local playbook install under `~/.claude-playbooks/`,
  not just one — a pilot commonly runs several playbook installs from one
  herdr session, one per client/project, and a tab can resolve to any of them.
- `snapshot.py`/`resurrect.py` existed in an earlier version of this skill and
  were deliberately removed; don't recreate them as a "convenience" without
  re-litigating why (the gotchas above are the reason, found by actually
  running the scripted version against a real 70-tab crash recovery).
