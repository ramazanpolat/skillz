# Release skillz

For the maintainer. A release is a version in both manifests, a CHANGELOG entry,
and an annotated tag `vX.Y.Z` on `main`.

1. On the branch, bump `version` in `plugins/skillz/.claude-plugin/plugin.json`
   and `metadata.version` in `.claude-plugin/marketplace.json`, and add a
   `## [vX.Y.Z] -- YYYY-MM-DD` entry to `CHANGELOG.md`.
2. `tests/run-all.sh` passes. With a TypeSafe key, so does
   `tests/run-all.sh --live` (the procedure-set evals against Jev).
3. Review, merge to `main`.
4. On `main`: `./release.sh vX.Y.Z`. It refuses unless the tree is clean and
   matches `origin/main`, both manifests say the version, the CHANGELOG has its
   entry, the docs standard holds (README, docs/, examples/, AGENTS.md; see
   [AGENTS.md](../../AGENTS.md#before-any-release)), and the offline tests
   pass. Then it tags and pushes the tag.
5. Users pick it up with `claude plugin marketplace update skillz` and
   `claude plugin update skillz@skillz`.
