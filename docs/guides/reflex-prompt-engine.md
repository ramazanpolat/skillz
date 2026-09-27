# Keep standing rules in REFLEXES.md (the prompt engine)

The `reflex` skill's original engine, for a config dir without a TypeSafe key,
or for conditions no event carries (a session starting, time passing). Every
active entry lives in `<config>/REFLEXES.md`, which `CLAUDE.md` imports, so it is
in the prompt from the first turn, and Claude matches it by its own judgment.

- **Set up and add:** ask for the rule ("whenever a session starts, tell me my
  open TODO count"). The skill resolves the config dir, creates `REFLEXES.md` with
  its firing rules, adds the `@REFLEXES.md` import, shows the draft entry, and
  writes it on your yes. It applies from the next session.
- **Manage:** `list`, `all`, `pause <name>`, `resume <name>`, `remove <name>`,
  `fired <name>`.
- **Cost:** every active entry is in every session's prompt. Keep the set small;
  past a dozen, prune or move entries to procedures
  ([the jev engine](reflex-procedures.md)).

The full rules (the import traps, the entry shape, the firing rules) are in the
skill itself: [`skills/reflex/SKILL.md`](../../plugins/skillz/skills/reflex/SKILL.md),
section *Prompt engine*.
