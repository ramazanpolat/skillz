#!/usr/bin/env bash
#
# transfer.sh — push/pull files to/from a remote host over passwordless SSH.
#
# Relies on an SSH host alias that already authenticates without a password
# (key-based auth). Defaults to the host "macminim".
#
# Usage:
#   transfer.sh push <local-path> [remote-dest]     # local  -> remote
#   transfer.sh pull <remote-path> [local-dest]     # remote -> local
#   transfer.sh ls   [remote-path]                  # list a remote dir
#
# Options (before or after the subcommand):
#   -H, --host <alias>   Override the remote host (default: $SKILLZ_HOST or macminim)
#   -n, --dry-run        Show what would transfer, change nothing
#   -h, --help           Show this help
#
# Defaults:
#   push remote-dest -> ~/ (remote home)
#   pull local-dest  -> . (current directory)
#
# Examples:
#   transfer.sh push ./report.pdf                 # -> macminim:~/report.pdf
#   transfer.sh push ./build/ ~/deploys/app/      # dir (trailing slash = contents)
#   transfer.sh pull ~/logs/app.log ./logs/       # macminim -> ./logs/
#   transfer.sh -H macmini2 push ./data.csv
#   SKILLZ_HOST=macmini2 transfer.sh pull ~/out.txt

set -euo pipefail

HOST="${SKILLZ_HOST:-macminim}"
DRY=""
ARGS=()

while [ $# -gt 0 ]; do
  case "$1" in
    -H|--host) HOST="$2"; shift 2 ;;
    -n|--dry-run) DRY="--dry-run"; shift ;;
    -h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done

set -- "${ARGS[@]:-}"
cmd="${1:-}"

die() { echo "transfer: $*" >&2; exit 1; }

# rsync flags: archive, compress, human-readable, partial+progress.
RSYNC=(rsync -avzh --partial --progress -e ssh)
[ -n "$DRY" ] && RSYNC+=("$DRY")

case "$cmd" in
  push)
    src="${2:-}"; dest="${3:-~/}"
    [ -n "$src" ] || die "push needs a local path. See --help."
    [ -e "$src" ] || die "local path not found: $src"
    echo "==> push  $src  ->  $HOST:$dest"
    "${RSYNC[@]}" "$src" "$HOST:$dest"
    ;;
  pull)
    src="${2:-}"; dest="${3:-.}"
    [ -n "$src" ] || die "pull needs a remote path. See --help."
    echo "==> pull  $HOST:$src  ->  $dest"
    "${RSYNC[@]}" "$HOST:$src" "$dest"
    ;;
  ls)
    path="${2:-~/}"
    ssh "$HOST" "ls -lah -- $path"
    ;;
  ""|-h|--help)
    sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
    ;;
  *)
    die "unknown subcommand: $cmd (expected push|pull|ls). See --help."
    ;;
esac
