#!/usr/bin/env bash
# Release skillz: check, then tag vX.Y.Z on main and push the tag.
#
# Usage: ./release.sh vX.Y.Z
#
# Refuses unless: on main, clean, equal to origin/main; the tag is new; both
# manifests say X.Y.Z; CHANGELOG.md has `## [vX.Y.Z]`; the docs standard holds
# (AGENTS.md, "Before any release"); tests/run-all.sh passes. The version bump and
# the CHANGELOG entry land in the PR, not here: this script only verifies and tags.
set -euo pipefail
TAG="${1:-}"
[[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Usage: $0 vX.Y.Z" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")" && pwd)"; cd "$ROOT"
die() { echo "release: $*" >&2; exit 1; }

[ "$(git branch --show-current)" = main ] || die "not on main"
[ -z "$(git status --porcelain)" ] || die "the working tree is not clean"
git fetch -q origin main --tags
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || die "main is not origin/main"
git rev-parse -q --verify "refs/tags/$TAG" >/dev/null && die "tag $TAG exists already"

V="${TAG#v}"
[ "$(python3 -c 'import json;print(json.load(open("plugins/skillz/.claude-plugin/plugin.json"))["version"])')" = "$V" ] \
  || die "plugins/skillz/.claude-plugin/plugin.json version is not $V"
[ "$(python3 -c 'import json;print(json.load(open(".claude-plugin/marketplace.json"))["metadata"]["version"])')" = "$V" ] \
  || die ".claude-plugin/marketplace.json metadata.version is not $V"
grep -q "^## \[$TAG\]" CHANGELOG.md || die "CHANGELOG.md has no '## [$TAG]' entry"

missing=()
[ -f README.md ] || missing+=("README.md")
if [ -f README.md ]; then
  for h in "What it is" "Why it exists" "How it is used" "Where next"; do
    grep -q "^## $h" README.md || missing+=("README.md: '## $h'")
  done
  [ "$(wc -l < README.md)" -le 120 ] || missing+=("README.md: over 120 lines")
fi
[ -f docs/README.md ] || missing+=("docs/README.md")
for d in tutorials guides reference; do
  ls docs/$d/*.md >/dev/null 2>&1 || missing+=("docs/$d/ (no pages)")
done
[ -f examples/README.md ] || missing+=("examples/README.md")
n=0
for e in examples/[0-9][0-9]-*/; do
  [ -d "$e" ] || continue
  n=$((n + 1))
  [ -f "$e/README.md" ] || missing+=("${e}README.md")
done
[ "$n" -gt 0 ] || missing+=("examples/NN-*/ (no examples)")
grep -q '^## Before any release' AGENTS.md 2>/dev/null || missing+=("AGENTS.md: '## Before any release'")
if [ ${#missing[@]} -gt 0 ]; then
  printf 'release: the docs standard is not met; missing:\n' >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi

bash tests/run-all.sh >/dev/null || die "tests/run-all.sh fails; run it to see why"

git tag -a "$TAG" -m "skillz $TAG"
git push -q origin "$TAG"
echo "Released $TAG at $(git rev-parse --short HEAD)."
