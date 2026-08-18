#!/usr/bin/env bash
# Provision a Sprite VM as an isolated test environment for a target repo.
#
# Provisioning is interactive: you authenticate Claude and GitHub by hand in the
# herdr console pane, between the scripted stages below. See SKILL.md for the
# full choreography.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "$HERE/lib.sh"

usage() {
  cat <<'USAGE'
Usage:
  provision.sh ensure <target> [seed flags]
  provision.sh checkpoint <target> <claude-auth|ready>

Seed flags (written to config; only needed the first time, or to change a value):
  --repo-url URL     git URL to clone inside the sprite (required)
  --branch B         branch to test (default: main)
  --sprite NAME      sprite name (default: test-<target>)
  --clone-dir DIR    dir name to clone into (default: repo basename)
  --install-cmd CMD  install command, run from the clone dir (default: ./install.sh)
  --test-cmd CMD     test command, run from the clone dir (default: empty)

Stages (run with manual auth in the pane BETWEEN them):
  ensure                  seed/verify config, create-or-reuse the sprite, open a console pane,
                          print the network egress policy
  checkpoint claude-auth  snapshot after you authenticate Claude in the pane
  checkpoint ready        snapshot after you authenticate GitHub; saves the reset point to config
USAGE
  exit "${1:-0}"
}

[ $# -ge 2 ] || usage 1
cmd="$1"; target="$2"; shift 2

case "$cmd" in
  ensure)
    # Seed any provided flags into the config.
    while [ $# -gt 0 ]; do
      case "$1" in
        --repo-url)    tos_cfg_set "$target" repo_url    "$2"; shift 2 ;;
        --branch)      tos_cfg_set "$target" branch      "$2"; shift 2 ;;
        --sprite)      tos_cfg_set "$target" sprite      "$2"; shift 2 ;;
        --clone-dir)   tos_cfg_set "$target" clone_dir   "$2"; shift 2 ;;
        --install-cmd) tos_cfg_set "$target" install_cmd "$2"; shift 2 ;;
        --test-cmd)    tos_cfg_set "$target" test_cmd    "$2"; shift 2 ;;
        *) tos_die "unknown flag: $1" ;;
      esac
    done

    # Defaults for anything still unset.
    repo_url="$(tos_cfg_get "$target" repo_url)"
    [ -n "$repo_url" ] || tos_die "no repo_url for '$target' — pass --repo-url on first ensure"
    [ -n "$(tos_cfg_get "$target" branch)" ]   || tos_cfg_set "$target" branch main
    [ -n "$(tos_cfg_get "$target" sprite)" ]   || tos_cfg_set "$target" sprite "test-$target"
    if [ -z "$(tos_cfg_get "$target" clone_dir)" ]; then
      base="$(basename "$repo_url")"; tos_cfg_set "$target" clone_dir "${base%.git}"
    fi
    [ -n "$(tos_cfg_get "$target" install_cmd)" ] || tos_cfg_set "$target" install_cmd "./install.sh"

    sprite="$(tos_cfg_get "$target" sprite)"
    tos_sprite_ensure "$sprite"

    tos_info "network egress policy for '$sprite':"
    tos_network_policy "$sprite" >&2

    pane="$(tos_pane_open)"
    tos_cfg_set "$target" pane "$pane"
    tos_pane_send "$pane" "sprite console -s $sprite"
    tos_info "opened console pane $pane (running 'sprite console -s $sprite')"

    cat >&2 <<NEXT

Next (do these in pane $pane):
  1. Authenticate Claude:  run 'claude' and complete login.
  2. Then:                 provision.sh checkpoint $target claude-auth
  3. Authenticate GitHub:  gh auth login --git-protocol https --web
  4. Then:                 provision.sh checkpoint $target ready
NEXT
    ;;

  checkpoint)
    [ $# -ge 1 ] || usage 1
    label="$1"
    sprite="$(tos_cfg_get "$target" sprite)"
    [ -n "$sprite" ] || tos_die "no sprite for '$target' — run 'ensure' first"
    case "$label" in
      claude-auth)
        tos_checkpoint_create "$sprite" "test-on-sprite: claude authenticated" >/dev/null
        tos_info "checkpoint created: claude authenticated"
        ;;
      ready)
        id="$(tos_checkpoint_create "$sprite" "test-on-sprite: ready (github authenticated)")"
        [ -n "$id" ] || tos_die "could not resolve new checkpoint id"
        tos_cfg_set "$target" ready_checkpoint "$id"
        tos_info "ready checkpoint $id saved — this is the reset point for test runs"
        ;;
      *) tos_die "unknown checkpoint label: $label (use claude-auth or ready)" ;;
    esac
    ;;

  -h|--help|help) usage 0 ;;
  *) tos_die "unknown command: $cmd (use ensure or checkpoint)" ;;
esac
