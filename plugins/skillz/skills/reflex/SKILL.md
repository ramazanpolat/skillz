---
name: reflex
description: "Standing \"whenever X happens, do Y\" instructions -- a condition plus the steps to follow -- that fire on their own in later sessions. Two engines. jev: each instruction is a procedure file, and a hook asks TypeSafe's Jev on every eligible event (the user's message, a shell command, a file write or edit, an outgoing message, the final reply) whether one applies and injects its steps; nothing sits in the prompt. prompt: entries in a REFLEXES.md that CLAUDE.md imports, matched by Claude's own judgment. Use when the user wants something to happen automatically from now on (\"whenever I open a PR, ...\", \"from now on, before any release, ...\", \"whenever I mention X, log it\"), and to manage them: list, pause, resume, remove, test, log, check, migrate, setup. Also use when the user says reflex, procedure, standing instruction or standing rule. Not for a one-off reminder in this conversation. Condition-triggered, unlike a cron (time) or a plain settings.json hook (an exact tool event running a script)."
---

# reflex

A **reflex** is a standing stimulus/response instruction: a condition in
natural language, and what to do whenever it holds. It belongs to no project
and applies to every session of the config dir until paused.

There are two engines. Each run, find out which one this config dir uses
(below) and follow that section.

| | **jev** (procedures) | **prompt** (REFLEXES.md) |
|---|---|---|
| Where an entry lives | one file per procedure, `<config>/procedures/<name>.md` | one `##` section of `<config>/REFLEXES.md` |
| Standing prompt cost | none | every entry, plus the firing rules, in every session |
| Who decides it applies | Jev (TypeSafe System One), on every eligible event, via a hook | Claude's own judgment, when it remembers to check |
| When it can fire | the user's message, a shell command, a file write or edit, an outgoing agent message, the final reply | any condition Claude can notice |
| Needs | a TypeSafe API key, python3; event text goes to api.typesafe.ai | nothing |

**Prefer jev** when a key is available and the config dir's data rules allow
sending session content to TypeSafe. Use **prompt** otherwise, and for
conditions no event carries (the passage of time, a session merely starting).

## Which engine is in use

```bash
C="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"; case "$C" in /*) ;; *) C="$PWD/$C";; esac
test -f "$C/procedures/config.json" && echo "jev $C" || echo "prompt $C"
```

Run it; do not assume `~/.claude`. `jev` -> the **Jev engine** section.
`prompt` -> the **Prompt engine** section, unless the user asks to set up jev.

The dispatcher is `scripts/dispatch.py` in this skill's base directory (the
path shown when the skill loads). Call it as `python3 <base>/scripts/dispatch.py`.
If `CLAUDE_CONFIG_DIR` is not set in your shell but the session uses another
config dir, pass `REFLEX_PROCEDURES_DIR=<config>/procedures` to it.

## Jev engine (procedures)

### How a procedure fires

The skillz plugin ships a hook on `UserPromptSubmit`, `PreToolUse` (Bash,
Write, Edit, MultiEdit, NotebookEdit, SendMessage) and `Stop`. It is a no-op
unless `<config>/procedures/config.json` exists. When it does:

1. The event becomes a **kind** and its text: `user_prompt`, `bash` (the
   command), `write` / `edit` (file path and new text), `message` (an outgoing
   SendMessage), `reply` (the final reply). Long text is clipped; values that
   look like credentials are redacted.
2. Only active procedures whose `fires_on` includes that kind are **eligible**.
   None -> no call at all.
3. One Jev Choice question: which eligible procedure applies to this moment,
   or `none`. About 0.3 s and 700 input tokens.
4. At `p >= fire` (default 0.8) the procedure's steps are injected as context
   the first time in a session, and a one-line reminder after that. Between
   `hint` (0.5) and `fire`, a one-line hint. Below, nothing.
5. On `reply`, a confident match **blocks** the reply once, with the steps as
   the reason, so the reply is fixed before the user sees it. Never twice for
   the same turn.
6. Every decision goes to `<config>/procedures/decisions.jsonl` (kind, choice,
   p, action, latency, a 120-character preview). That log is the evidence.

It fails open: no key, an error or a slow answer means nothing is injected and
the work goes on. A procedure never blocks a tool call.

When a procedure's text appears in your context (`[procedure: <name>] Jev
matched this moment ...`), do what it says: disclose it at the top of the reply
as `[procedure: <name>] firing: <reason>`; in mode `auto` follow the steps and
report; in mode `ask` state the match and the proposed steps and wait for the
user; in read-only mode do nothing and say it would have fired.

### Setup (`setup jev`)

1. **Data rules first.** Read `<config>/CLAUDE.md`, `<config>/CLAUDE.local.md`
   and anything they import for rules about what may leave the machine (a
   gateway whose terms allow corpus use, "never send ... to third parties",
   governance sections). If any would forbid sending prompts, commands or
   replies to TypeSafe, stop, quote the rule, and do not set up jev.
2. **Say what leaves the machine, and get a yes:** for every eligible event,
   its text (the user's message, the shell command, the file path and new
   text, the outgoing message, the final reply) goes to `api.typesafe.ai`,
   clipped and with credential-looking values redacted, best effort. Only
   procedures' kinds are eligible, so a config with no `bash` procedure sends
   no commands.
3. **The key, by reference.** Never ask for the value. Ask where it is stored.
   If `with-secret` is installed:
   `with-secret --check TYPESAFE_API_KEY=keychain:typesafe` (or the reference
   the user names). `MISSING` -> ask the user to run `with-secret --store
   typesafe` themselves. Without `with-secret`, the key must be in the
   environment Claude Code starts with (`TYPESAFE_API_KEY`); never write it
   into `settings.json` or any file.
4. Write `<config>/procedures/config.json`:
   ```json
   {"engine": "jev", "model": "jev-latest", "fire": 0.8, "hint": 0.5,
    "timeout_s": 2.5, "key_ref": "keychain:typesafe"}
   ```
   Leave out `key_ref` when the key comes from the environment. The directory
   is outside the working directory, so the write may need approval.
5. Run `python3 <base>/scripts/dispatch.py check`. It prints the config, parses
   every procedure, and makes one live call.
6. If `<config>/REFLEXES.md` has entries, offer `migrate`.

Tell the user the hook reads the directory on every event, so a new procedure
applies from the next event, not the next session.

### Procedure file

`<config>/procedures/<name>.md`, the name lowercase-with-dashes and the same as
the file name:

```markdown
---
name: open-pr
title: Opening a pull request
mode: auto
status: active
fires_on: [bash, user_prompt]
covers: Creating a pull request now: running gh pr create, or the user asks to open one.
excludes: Viewing, listing or discussing existing PRs; the user saying not to open one.
---
1. Request `@codex review` once, in the PR body.
2. After creating it, report the head only as read back: `gh pr view <n> --json headRefOid,mergeable`.
```

- `fires_on`: any of `user_prompt`, `bash`, `write`, `edit`, `message`, `reply`.
- `covers`: the exact condition, as one line. Jev reads it literally.
- `excludes`: the near-misses that must not fire. Most wrong fires are fixed here.
- `mode`: `auto` (follow, then report) or `ask` (propose, wait). `ask` for
  anything that commits, deletes, installs or touches something remote.
- `status`: `active` or `paused`.
- One `key: value` per line; lists as `[a, b]`; no multi-line values.
- The body: the steps, as numbered lines. Say how to report at the end if it matters.

### Routing (jev)

Find the intent word -- `list`, `all`, `add`, `pause`, `resume`, `remove`,
`test`, `log`, `check`, `migrate`, `setup` -- anywhere in the request, not only
first. Anything else is an `add` description.

- **list / all**: `dispatch.py list` (status, mode, kinds, fires from the log).
- **add <description>**: draft, tune, confirm, write (below).
- **pause / resume <name>**: edit `status:` in its file. Confirm in one line.
- **remove <name>**: show the file and confirm first. If the log shows it has
  fired, say so and offer `pause` instead. Paste the file into your reply
  before deleting it: the transcript is the only copy.
- **test "<text>" [kind]**: `dispatch.py test <kind> "<text>"` (default kind
  `user_prompt`). A dry run: nothing is injected, logged or remembered.
- **log [N]**: `dispatch.py log N`.
- **check**: `dispatch.py check`.
- **migrate**: below.

### Adding a procedure

Every procedure is a trigger Jev evaluates on its kinds' every event, so draft
it, tune it, and get a yes before writing.

1. **Name** verb-led, 2-4 words. **Kinds**: the fewest that carry the moment.
   "Before X is done" is usually the command that does X (`bash`, `write`); "when
   the user asks for X", `user_prompt`; "when telling someone Y", `message` and
   `reply`.
2. **covers / excludes**: the exact condition and its near-misses. Jev reads
   literally: `git tag` in `covers` also matches `git tag -l` unless `excludes`
   says listing tags does not count.
3. **Tune before writing.** Draft 3 events that must fire and 3 near-misses that
   must not, as `[[kind, text, expected], ...]` with `expected` the procedure
   name or `none`. Evaluate the draft in a scratch directory, so it cannot fire
   in the meantime: copy `config.json` and the draft (as `status: active`) into
   it and run `REFLEX_PROCEDURES_DIR=<scratch> python3 <base>/scripts/dispatch.py
   eval <events.json>`. Sharpen `covers` / `excludes` until every line is right.
   Never lower `fire` to make a case pass.
4. Show the draft, the eval result and the kinds (so the user sees which events
   will now reach TypeSafe). On a yes, write the file, and save the events as
   `<config>/procedures/evals/<name>.json`: they are the regression test when
   the procedure changes later.

### Migrating from REFLEXES.md (`migrate`)

For each active entry: `Stimulus` -> `covers` (tightened) plus `excludes`;
pick `fires_on`; `Response` and `Report` -> the steps; keep the mode. Entries
whose stimulus no event carries (a session starting, time passing) stay in
REFLEXES.md. Tune each as in **Adding**. Then, with the user's yes, remove the
migrated sections from REFLEXES.md; if none remain, remove the `@REFLEXES.md`
line from CLAUDE.md and keep the file as `REFLEXES.md.migrated`. Never delete it.

### Limits

- Only the six kinds can trigger. A condition that no message, command, file
  change or reply carries belongs to the prompt engine, a cron, or a plain hook.
- Jev is calibrated, not infallible, and literal. `decisions.jsonl` shows every
  call; judge a procedure by what its steps produced, not by the log's `fire`.
- Each eligible event waits about 0.3 s for Jev.
- The hook reads `CLAUDE_CONFIG_DIR` (or `~/.claude`); procedures are per
  config dir.

## Prompt engine (REFLEXES.md)

### How it works, and why it must be a file import

A skill's body is not in context until the skill is invoked — only its
description is. So a skill alone cannot make a reflex fire: nothing would be
watching. What makes this work is a file the user's `CLAUDE.md` imports, so the
entries are in the prompt from the first turn of every session.

`@` imports resolve **one literal filename**. `@dir/one.md` works; `@dir/` and
`@dir/*.md` bring in no content. So all entries live in one file, `REFLEXES.md`,
and there is no compile step, no per-entry file, and nothing to generate.

(Importing a *missing* file fails differently, and worse: the import is not
dropped, the raw `@REFLEXES.md` line is left sitting in the prompt where it reads
as a missing instruction set. Hence the rule below about never adding the import
without creating the file.)

Nested imports do work (verified three levels deep), so `REFLEXES.md` can be
reached through an intermediate file if a setup already has one.

### Setup (do this before writing the first entry)

**Resolve the config directory by running this — do not assume `~/.claude`:**

```bash
echo "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
```

Anyone running more than one Claude Code configuration side by side sets
`CLAUDE_CONFIG_DIR`, and writing to `~/.claude` there puts the reflexes in a
directory that session never reads. Run the command; use what it prints. If it
prints a relative path, resolve it to an absolute one first — otherwise
`REFLEXES.md` lands under whatever directory that one session started in.

Then, with `<config>` as that path:

1. If `<config>/REFLEXES.md` does not exist, create it with the **Standing
   header** below. If it exists but has no `## Firing rules` section, insert the
   header above its entries — a file can arrive from elsewhere (a migration, a
   colleague, an older setup) carrying entries and no rules, and entries without
   rules never fire. Nothing in the file says so, and nothing errors: the reflexes
   are simply inert, which is the hardest failure to notice.
2. If `<config>/CLAUDE.md` does not already import it, add `@REFLEXES.md` on a
   line of its own. Create `CLAUDE.md` if absent. **Check whether the file ends
   in a newline first** — plenty of editors save without one, and a blind
   `>>` append then produces `Always be terse.@REFLEXES.md`, which corrupts the
   user's last line *and* kills the import, since `@` must begin the line. Read
   the file and write it back rather than appending blind.

Never add the import without creating the file. An unresolvable `@` import is
not silently dropped — the raw `@REFLEXES.md` line is left sitting in the system
prompt, which reads as a missing instruction set.

**Both files are outside the working directory, so the write may need the
user's approval, and it can be refused.** Do the two steps in this order —
`REFLEXES.md` first, `CLAUDE.md` second — so a refusal midway leaves a stray
file rather than a dangling import. If either write is denied, say plainly that
reflexes cannot fire without the import, and offer to print both pieces for the
user to paste in themselves.

**Re-check both halves on every run, not only the first.** If the `CLAUDE.md`
edit was refused once, `REFLEXES.md` still exists — so a later run sees the file,
concludes setup is done, and writes entries that can never fire, silently.
Confirm the file exists *and* that `CLAUDE.md` imports it before drafting
anything, and repair whichever half is missing.

Tell the user, in one line, that entries take effect from the **next** session:
`CLAUDE.md` is assembled at startup, so an entry added mid-session is not in the
current context.

#### Standing header

`REFLEXES.md` starts with the rules, because the rules must be in context
wherever the entries are:

```markdown
# Reflexes

Standing stimulus/response entries. You match each Stimulus below against what
actually happens in this session; nothing polls and no script decides anything.

## Firing rules (MANDATORY)

1. **Check before your first reply, every session**, and again whenever
   something notable happens. This is the step that gets skipped. A reflex is
   not a note to keep in mind should it become relevant — it is a standing
   check. A Stimulus that is the session beginning is satisfied by your first
   turn itself; the user opening with something unrelated is the normal case,
   not a reason to skip. Fire, then answer what they asked.
2. **Match honestly.** Do not stretch a match — a reflex firing on loosely
   related events is noise. This governs whether a condition holds; it is not a
   reason to defer rule 1.
3. **Disclose at the top of your reply, naming the reflex**: `[reflex: <name>]
   firing — <one-line reason>`. Nothing the user asked for produced this work,
   so folding it into the body of an answer hides it.
4. **Act by mode.** `[auto]` — run the Response, then report. `[ask]` — state
   the match and the proposed Response, then **wait**; begin no step.
5. **Once per session** per reflex, unless the entry's own Stimulus says
   otherwise. A counting reflex must waive this explicitly in its Stimulus.
6. **No chaining.** A reflex's Response never triggers another reflex.
7. **Never when the user has asked for read-only mode.** Say it would have
   fired and what it would have done.

Firing is a judgment call, not a guarantee, so a counting reflex is not an exact
counter — a missed session is a silently low number. Have the Response write its
own evidence and read that, not the `**Log:**` line.

## Entries
```

### Entry shape

Each entry is one `##` section under `## Entries`:

```markdown
## reflex: <name> [auto|ask] [paused]

<one-line title>

**Stimulus:** <the condition, self-contained>

**Response:**
1. <step>
2. <step>

**Report:** <what to tell the user afterwards>

**Log:** fired 0 times
```

`[paused]` in the heading means it does not fire — leave the section in place
and add or remove that one word.

### Routing

Find the **intent word** — `list`, `all`, `add`, `pause`, `resume`, `remove`,
`fired` — rather than reading only the first word. Requests arrive as "reflex
pause log-errors" or "please list my reflexes", and taking word one literally
turns both into a request to *create* a reflex named after the command. Skip a
leading `reflex` and any politeness, then match. Every branch is a Read plus an
Edit of `REFLEXES.md`; never shell out.

**Nothing, or "list"** — list active entries: name, mode, title, `**Log:**`.
Mention paused ones only if any exist.

**"all"** — same, including paused.

**"add <description>"** — draft, confirm, write. See below.

**"pause <name>" / "resume <name>"** — Edit the heading to add or remove
`[paused]`. Confirm in one line.

**"remove <name>"** — show the entry and confirm first. If its `**Log:**` shows
it has fired, say so and offer `pause` instead. There is no archive, so paste
the section into your reply before removing it — the transcript is the only copy.

**"fired <name> [outcome]"** — Edit that entry's `**Log:**`: bump the count and
append `; last: <YYYY-MM-DD-HH_MM> <outcome>`. Draft the outcome from the
session if none was given.

**Anything else** — treat the whole string as an `add` description.

### Drafting an entry

Every active entry costs system-prompt tokens in every future session, so show
the draft and get confirmation before writing.

1. **Build what was asked.** Any condition the user can describe is valid,
   including a plain session event. Never refuse one because it could have been
   a hook. When the trigger *is* a deterministic tool event **and** the action is
   purely mechanical — a counter that must never miss, a formatter, blocking a
   write — say in one line that a `settings.json` hook would be exact and cost no
   context, offer to write one, then build whatever they chose. Default to the
   reflex they asked for: a hook's action is a shell script, while a reflex's
   Response is arbitrary work in prose, which is most of what people want.
2. **Name** lowercase-with-dashes, verb-led, 2–4 words.
3. **Mode** `auto` when the Response only reads, appends to its own log, and
   reports; `ask` when it commits, installs, deletes, or touches anything
   remote. A reflex that fires often should lean `auto` — an `ask` prompting on
   every occurrence defeats passive logging and gets paused within a week.
4. **Tighten the Stimulus** so it makes sense to someone who was not in this
   conversation and does not match everything. If it must fire more than once
   per session, put that waiver in the Stimulus itself.
5. **Say what is not guaranteed** when they are counting something.
6. **Check where the Response writes.** A Response that writes outside the
   session's working directory is blocked by the file sandbox and needs approval
   every time — and a reflex whose whole job is passive logging is worthless if
   it prompts on each firing. This is measured, not theoretical: a reflex logging
   to `~/mentions.log` fired correctly in a project directory and could not
   write, session after session.

   So when drafting a Response that writes, ask where, and offer the options
   plainly:
   - a path **inside the directory the user works in** — always writable, but
     per-project;
   - a path under the config dir or `$HOME` — one place for everything, but it
     needs a permission rule (`"Write(/Users/you/**)"` in `settings.json`
     `permissions.allow`, or running with a permissive mode) or it will be
     denied;
   - **no file at all** — the Response just reports in the reply, which needs no
     permission and is often what the user actually wanted.
7. **Write it** under `## Entries`, then state that it is live from the next
   session.

### Notes

- Never leave a half-written entry active. If the Stimulus or Response is still
  a placeholder, mark the heading `[paused]`.
- Two sessions editing `REFLEXES.md` at once can clobber each other — Edit is
  read-modify-write with no lock. Re-Read immediately before editing.
- Rule 3 asks for the disclosure line, and rightly: naming the reflex is how the
  user sees that unrequested work happened. But it drifts — entries have been
  observed firing and doing the work while reporting only the outcome. So ask for
  it and do not *depend* on it: to check whether a reflex is working, read what
  its Response wrote, never the announcement and never the `**Log:**` counter,
  which is a convenience for the user rather than evidence.
- Keep the set small. Every entry is in context forever; past a dozen, pause or
  prune rather than accumulate.
