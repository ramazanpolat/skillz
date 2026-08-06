---
name: reflex
description: "Standing \"whenever X happens, do Y\" instructions that fire on their own in later sessions. Use when the user wants something to happen automatically from now on — \"whenever I mention X, log it\", \"whenever a session starts, tell me my counts\", \"whenever the same error shows up a third time, open a TODO\", \"remind me to X every time Y\" — and for managing those entries: list, pause, resume, remove, or record that one fired. Also use when the user says reflex, standing instruction, or standing rule. A reflex is condition-triggered, unlike a cron (time-triggered) or a hook (tool-event-triggered, exact, configured in settings.json)."
---

# reflex

A **reflex** is a standing stimulus/response entry: a condition in natural
language plus the action to take whenever it is observed. It belongs to no
project and applies to every session until paused.

Reflexes are **model-evaluated**. Nothing polls, nothing watches a file, and no
script decides anything. Every active entry is imported into the system prompt,
and Claude matches its Stimulus against what actually happens in the session.

## How it works, and why it must be a file import

A skill's body is not in context until the skill is invoked — only its
description is. So a skill alone cannot make a reflex fire: nothing would be
watching. What makes this work is a file the user's `CLAUDE.md` imports, so the
entries are in the prompt from the first turn of every session.

`@` imports resolve **one literal filename**. Directories and globs import
nothing, silently — `@dir/` and `@dir/*.md` both fail, while `@dir/one.md`
works. So all entries live in one file, `REFLEXES.md`, and there is no compile
step, no per-entry file, and nothing to generate.

Nested imports do work (verified three levels deep), so `REFLEXES.md` can be
reached through an intermediate file if a setup already has one.

## Setup (do this before writing the first entry)

**Resolve the config directory by running this — do not assume `~/.claude`:**

```bash
echo "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
```

Anyone running more than one Claude Code configuration side by side sets
`CLAUDE_CONFIG_DIR`, and writing to `~/.claude` there puts the reflexes in a
directory that session never reads. Run the command; use what it prints.

Then, with `<config>` as that path:

1. If `<config>/REFLEXES.md` does not exist, create it with the **Standing
   header** below.
2. If `<config>/CLAUDE.md` does not already import it, append `@REFLEXES.md` on
   its own line. Create `CLAUDE.md` if absent.

Never add the import without creating the file. An unresolvable `@` import is
not silently dropped — the raw `@REFLEXES.md` line is left sitting in the system
prompt, which reads as a missing instruction set.

**Both files are outside the working directory, so the write may need the
user's approval, and it can be refused.** Do the two steps in this order —
`REFLEXES.md` first, `CLAUDE.md` second — so a refusal midway leaves a stray
file rather than a dangling import. If either write is denied, say plainly that
reflexes cannot fire without the import, and offer to print both pieces for the
user to paste in themselves.

Tell the user, in one line, that entries take effect from the **next** session:
`CLAUDE.md` is assembled at startup, so an entry added mid-session is not in the
current context.

### Standing header

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

## Entry shape

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

## Routing

Parse the first word of the request. Every branch is a Read plus an Edit of
`REFLEXES.md`; never shell out.

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

## Drafting an entry

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
     needs a permission rule (`"Write(//Users/you/**)"` in `settings.json`
     `permissions.allow`, or running with a permissive mode) or it will be
     denied;
   - **no file at all** — the Response just reports in the reply, which needs no
     permission and is often what the user actually wanted.
7. **Write it** under `## Entries`, then state that it is live from the next
   session.

## Notes

- Never leave a half-written entry active. If the Stimulus or Response is still
  a placeholder, mark the heading `[paused]`.
- Two sessions editing `REFLEXES.md` at once can clobber each other — Edit is
  read-modify-write with no lock. Re-Read immediately before editing.
- The disclosure line in rule 3 is convention and drifts in practice: entries
  have been observed firing and doing the work while reporting only the outcome.
  The Response's own written output is the dependable evidence, not the
  announcement and not the `**Log:**` counter.
- Keep the set small. Every entry is in context forever; past a dozen, pause or
  prune rather than accumulate.
- **Kommander users:** that playbook ships its own `reflex` skill wired to
  `REFLEX-OPS.md` in the Kommander config dir. Use that one there; this skill is
  the standalone equivalent for a plain Claude Code install.
