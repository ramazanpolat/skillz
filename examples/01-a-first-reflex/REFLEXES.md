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

## reflex: todo-count-at-start [auto]

Tell the user their open TODO count when a session starts

**Stimulus:** The session begins (the first turn of any session).

**Response:**
1. Count the files in `~/todo/` whose names do not start with `DONE--`.

**Report:** One line at the top: "Open TODOs: <n>".

**Log:** fired 0 times
