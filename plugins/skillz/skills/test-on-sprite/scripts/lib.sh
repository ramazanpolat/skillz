#!/usr/bin/env bash
# Shared helpers for the test-on-sprite skill.
# Sourced by provision.sh and run-tests.sh. Sourcing has no side effects.
#
# All machine/repo specifics live in the JSON config (TOS_CONFIG), never here.

set -euo pipefail

# Config + logs live outside any repo so nothing sensitive is ever committed.
TOS_CONFIG="${TOS_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/test-on-sprite/config.json}"
TOS_LOG_DIR="${TOS_LOG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/test-on-sprite/logs}"

tos_die()  { echo "test-on-sprite: $*" >&2; exit 1; }
tos_info() { echo "[test-on-sprite] $*" >&2; }
tos_need() { command -v "$1" >/dev/null 2>&1 || tos_die "missing required command: $1"; }
tos_stamp(){ date +%Y-%m-%d-%H_%M; }

# ---------------------------------------------------------------------------
# Config (JSON, manipulated via python3)
# ---------------------------------------------------------------------------
tos_cfg_ensure_file() {
  tos_need python3
  if [ ! -f "$TOS_CONFIG" ]; then
    mkdir -p "$(dirname "$TOS_CONFIG")"
    printf '{\n  "targets": {}\n}\n' > "$TOS_CONFIG"
  fi
}

tos_cfg_get() { # <target> <key> -> prints value ("" if absent)
  tos_cfg_ensure_file
  python3 - "$TOS_CONFIG" "$1" "$2" <<'PY'
import json, sys
cfg, t, k = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(cfg))
print((d.get("targets", {}).get(t, {}) or {}).get(k, "") or "")
PY
}

tos_cfg_set() { # <target> <key> <value>
  tos_cfg_ensure_file
  python3 - "$TOS_CONFIG" "$1" "$2" "$3" <<'PY'
import json, sys
cfg, t, k, v = sys.argv[1:5]
d = json.load(open(cfg))
d.setdefault("targets", {}).setdefault(t, {})[k] = v
with open(cfg, "w") as f:
    json.dump(d, f, indent=2)
    f.write("\n")
PY
}

tos_cfg_has() { # <target> -> exit 0 if entry exists
  tos_cfg_ensure_file
  python3 - "$TOS_CONFIG" "$1" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if sys.argv[2] in d.get("targets", {}) else 1)
PY
}

tos_cfg_targets() {
  tos_cfg_ensure_file
  python3 - "$TOS_CONFIG" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print("\n".join(sorted(d.get("targets", {}).keys())))
PY
}

# Validate that the required keys exist for a target; tos_die otherwise.
tos_cfg_require() { # <target> <key...>
  local t="$1"; shift
  local k v
  for k in "$@"; do
    v="$(tos_cfg_get "$t" "$k")"
    [ -n "$v" ] || tos_die "config for '$t' missing '$k' — run: provision.sh ensure $t --$k ..."
  done
}

# ---------------------------------------------------------------------------
# Sprite
# ---------------------------------------------------------------------------
tos_sprite_exists() { sprite list 2>/dev/null | grep -Fxq "$1"; }

tos_sprite_ensure() { # <sprite>
  if tos_sprite_exists "$1"; then
    tos_info "sprite '$1' exists — reusing"
  else
    tos_info "creating sprite '$1'"
    sprite create "$1" --skip-console >&2
  fi
}

tos_sprite_exec() { # <sprite> <command-string>   (runs under bash -lc inside the sprite)
  local s="$1"; shift
  sprite exec -s "$s" -- bash -lc "$*"
}

tos_network_policy() { # <sprite> -> prints the egress policy
  tos_sprite_exec "$1" 'cat /.sprite/policy/network.json 2>/dev/null || echo "(no /.sprite/policy/network.json)"'
}

# Create a checkpoint and echo its version id (vN). List is newest-first.
tos_checkpoint_create() { # <sprite> <comment> -> echoes id
  local s="$1" c="$2"
  sprite checkpoint create -s "$s" --comment "$c" >&2
  tos_checkpoint_find "$s" "$c"
}

tos_checkpoint_find() { # <sprite> <comment-substring> -> echoes newest matching id ("" if none)
  local s="$1" c="$2"
  sprite checkpoint list -s "$s" 2>/dev/null | awk -v c="$c" '
    /^v[0-9]+/ { id=$1; $1=$2=$3=""; if (index($0, c)) { print id; exit } }'
}

tos_checkpoint_restore() { # <sprite> <version-id>
  sprite checkpoint restore -s "$1" "$2" >&2
}

# ---------------------------------------------------------------------------
# herdr panes
# ---------------------------------------------------------------------------
# Split a new pane to the right of THIS agent's pane and echo its id.
# Uses the explicit $HERDR_PANE_ID — never --current, which lands in the wrong tab.
tos_pane_open() { # [cwd] -> echoes new pane id
  local base="${HERDR_PANE_ID:-}"
  [ -n "$base" ] || tos_die "HERDR_PANE_ID not set — run this inside a herdr pane"
  herdr pane split "$base" --direction right --cwd "${1:-$PWD}" --no-focus 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["pane"]["pane_id"])'
}

tos_pane_send() { # <pane-id> <text>   (sends text + Enter)
  herdr pane send-text "$1" "$2" >/dev/null
  herdr pane send-keys "$1" Enter >/dev/null
}

tos_pane_read() { # <pane-id> [lines]
  herdr pane read "$1" --source recent --lines "${2:-40}"
}
