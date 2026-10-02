---
name: release
title: Tagging or releasing a version
mode: ask
fires_on: [bash, user_prompt]
covers: Creating a version tag or release now: release.sh, git tag -a / git tag <name>, pushing a version tag, gh release create, npm publish, publishing a marketplace version; or the user asks to tag or release.
excludes: Listing or reading tags (git tag -l), reading a CHANGELOG, questions about how releasing works.
---
1. Check the docs standard: a short README (what, why, how), docs/ with
   tutorials and guides, examples/ each with its own README, an AGENTS.md.
   If any is missing, stop and say so; never release without it.
2. Check the CHANGELOG has an entry for this version.
3. Check the test suite is green on this exact commit.
4. Only then tag, and report the tag as read back from the remote.
