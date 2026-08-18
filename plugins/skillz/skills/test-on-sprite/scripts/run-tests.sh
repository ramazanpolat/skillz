#!/usr/bin/env bash
# Run a target's tests inside its provisioned sprite: (optional restore) ->
# clone at branch -> install -> test. Captures every step to a log artifact.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "$HERE/lib.sh"

usage() {
  cat <<'USAGE'
Usage:
  run-tests.sh <target> [--restore|--no-restore] [--branch B]

  --restore      restore the 'ready' checkpoint first (clean slate). DESTRUCTIVE:
                 drops the sprite's current session. Confirm with the user first.
  --no-restore   skip restore (default). Tests run on top of current sprite state.
  --branch B     override the configured branch for this run.
USAGE
  exit "${1:-0}"
}

[ $# -ge 1 ] || usage 1
target="$1"; shift
restore=0; branch_override=""
while [ $# -gt 0 ]; do
  case "$1" in
    --restore)    restore=1; shift ;;
    --no-restore) restore=0; shift ;;
    --branch)     branch_override="$2"; shift 2 ;;
    -h|--help)    usage 0 ;;
    *) tos_die "unknown flag: $1" ;;
  esac
done

tos_cfg_has "$target" || tos_die "no config for '$target' — run provision.sh ensure first"
tos_cfg_require "$target" repo_url sprite clone_dir install_cmd

sprite="$(tos_cfg_get "$target" sprite)"
repo_url="$(tos_cfg_get "$target" repo_url)"
branch="${branch_override:-$(tos_cfg_get "$target" branch)}"; branch="${branch:-main}"
clone_dir="$(tos_cfg_get "$target" clone_dir)"
install_cmd="$(tos_cfg_get "$target" install_cmd)"
test_cmd="$(tos_cfg_get "$target" test_cmd)"
ready_ckpt="$(tos_cfg_get "$target" ready_checkpoint)"

mkdir -p "$TOS_LOG_DIR"
log="$TOS_LOG_DIR/test-on-sprite-$target-$(tos_stamp).log"
: > "$log"

fail=0
run_step() { # <label> <command-string>
  local label="$1"; shift
  echo "=== $label ===" | tee -a "$log"
  if tos_sprite_exec "$sprite" "$*" 2>&1 | tee -a "$log"; then
    echo "--- $label: PASS ---" | tee -a "$log"
  else
    local rc=${PIPESTATUS[0]}
    echo "--- $label: FAIL (exit $rc) ---" | tee -a "$log"
    fail=1
  fi
}

{
  echo "target=$target sprite=$sprite branch=$branch"
  echo "repo=$repo_url clone_dir=$clone_dir"
  echo "started=$(date)"
} | tee -a "$log"

if [ "$restore" = 1 ]; then
  [ -n "$ready_ckpt" ] || tos_die "--restore requested but no ready_checkpoint in config"
  tos_info "restoring '$sprite' to ready checkpoint $ready_ckpt (destructive)"
  tos_checkpoint_restore "$sprite" "$ready_ckpt"
fi

run_step "clone $branch" "rm -rf $clone_dir && git clone --branch $branch --depth 1 $repo_url $clone_dir"
run_step "install"       "cd $clone_dir && $install_cmd"
if [ -n "$test_cmd" ]; then
  run_step "test"        "cd $clone_dir && $test_cmd"
else
  echo "=== test: SKIPPED (no test_cmd configured) ===" | tee -a "$log"
fi

echo "finished=$(date)" | tee -a "$log"
if [ "$fail" = 0 ]; then
  tos_info "RESULT: PASS  (log: $log)"
else
  tos_info "RESULT: FAIL  (log: $log)"
fi
echo "$log"
exit "$fail"
