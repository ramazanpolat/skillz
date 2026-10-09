#!/usr/bin/env bash
# Offline checks for skillz: reflex dispatcher unit tests, docs links, the
# manifests, and shellcheck (when installed). --live also runs the procedure-set
# evals against Jev (needs a TypeSafe key: TYPESAFE_API_KEY, or with-secret with
# the examples' key_ref).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT" || exit 1
fail=0
run() { echo ""; echo "==> $*"; "$@" || { echo "FAILED: $*"; fail=1; }; }

run python3 plugins/skillz/skills/reflex/tests/test_dispatch.py
run python3 tests/docs-links.py
run python3 - <<'PY'
import json
m = json.load(open(".claude-plugin/marketplace.json"))
p = json.load(open("plugins/skillz/.claude-plugin/plugin.json"))
h = json.load(open("plugins/skillz/hooks/hooks.json"))
assert m["metadata"]["version"] == p["version"], (m["metadata"]["version"], p["version"])
assert set(h["hooks"]) == {"UserPromptSubmit", "PreToolUse", "Stop"}, h["hooks"].keys()
print(f"manifests: version {p['version']} in both; hooks.json valid")
PY
run python3 - <<'PY'
import hashlib
# An installed plugin is only plugins/skillz/, so the licence texts ship inside
# it: Apache-2.0 (apache.org's text, byte for byte) and NOTICE at its root,
# identical to the repository's; the AGPL text beside the herdr skill (which
# stays AGPL-3.0-or-later); the MIT notice beside grilling.
def read(p):
    with open(p, "rb") as f:
        return f.read()
apache = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
assert hashlib.sha256(read("LICENSE")).hexdigest() == apache, "LICENSE is not apache.org's Apache-2.0 text"
assert read("plugins/skillz/LICENSE") == read("LICENSE"), "plugins/skillz/LICENSE differs from LICENSE"
assert read("plugins/skillz/NOTICE") == read("NOTICE"), "plugins/skillz/NOTICE differs from NOTICE"
assert b"GNU AFFERO GENERAL PUBLIC LICENSE" in read("plugins/skillz/skills/herdr/LICENSE")[:200], "herdr/LICENSE is not the AGPL"
assert b"See LICENSE in this directory." in read("plugins/skillz/skills/herdr/SKILL.md"), "herdr/SKILL.md does not point at its AGPL text"
assert read("plugins/skillz/skills/grilling/LICENSE").startswith(b"MIT License\n\nCopyright (c) 2026 Matt Pocock"), "grilling/LICENSE is not its MIT notice"
print("licences: Apache-2.0 and NOTICE ship in the plugin; herdr's AGPL and grilling's MIT beside their skills")
PY
if command -v claude >/dev/null 2>&1; then
  run claude plugin validate plugins/skillz
  run claude plugin validate .
fi
if command -v shellcheck >/dev/null 2>&1; then
  run shellcheck release.sh tests/run-all.sh plugins/skillz/skills/reflex/scripts/hook.sh
else
  echo ""; echo "SKIP shellcheck (not installed)"
fi
if [ "${1:-}" = "--live" ]; then
  D=plugins/skillz/skills/reflex/scripts/dispatch.py
  for set in dev heldout; do
    run env REFLEX_PROCEDURES_DIR=examples/03-procedure-set/procedures python3 "$D" eval "examples/03-procedure-set/events-$set.json"
  done
  run env REFLEX_PROCEDURES_DIR=examples/02-a-first-procedure/procedures python3 "$D" eval examples/02-a-first-procedure/procedures/evals/remote-kill.json
fi
echo ""
if [ "$fail" = 0 ]; then echo "run-all: all passed"; else echo "run-all: FAILED"; fi
exit "$fail"
