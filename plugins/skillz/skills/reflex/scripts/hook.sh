#!/usr/bin/env bash
# reflex procedures: the hook entry for UserPromptSubmit, PreToolUse and Stop.
# A no-op in a few milliseconds unless this config dir opted in by creating
# procedures/config.json (the reflex skill's `setup jev`). Always exits 0: a
# procedure never blocks work, except a Stop block the dispatcher chooses.
cfg="${REFLEX_PROCEDURES_DIR:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}/procedures}/config.json"
[ -f "$cfg" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
python3 "$(dirname "${BASH_SOURCE[0]}")/dispatch.py" hook
exit 0
