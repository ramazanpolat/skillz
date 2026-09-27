# 01 -- A first reflex (the prompt engine)

**Shows:** the smallest standing rule. One entry in a `REFLEXES.md`, which a
config dir's `CLAUDE.md` imports, so Claude sees it from the first turn and
matches it by its own judgment. The condition here, "a session begins", is one
no event carries, so it belongs to the prompt engine rather than to procedures.

**Needs:** nothing but Claude Code.

**Run it** in a scratch config dir, never your own:

```zsh
S=$(mktemp -d)
cp REFLEXES.md "$S/"
printf '@REFLEXES.md\n' > "$S/CLAUDE.md"
mkdir -p ~/todo && touch ~/todo/buy-milk.md
CLAUDE_CONFIG_DIR="$S" claude -p "hello"     # needs a login for that config dir
```

**Expected:** the reply starts with
`[reflex: todo-count-at-start] firing — ...` and "Open TODOs: 1" (or your
count). A judgment call: it can miss, which is why the file's firing rules
insist on checking before the first reply.

**Clean up:** `rm -rf "$S"` (and `~/todo/buy-milk.md` if you made it).

The file is exactly what `/skillz:reflex add` writes: the standing header with
the firing rules, then one `## reflex:` section per entry.
