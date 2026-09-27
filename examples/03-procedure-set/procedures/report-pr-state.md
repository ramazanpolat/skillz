---
name: report-pr-state
title: Reporting a SHA or merge state
mode: auto
fires_on: [reply, message]
covers: A message or reply that states a commit SHA, PR head or merge state (MERGEABLE, merged) to someone, without saying it was just read back from the remote.
excludes: A reply that says the value was read back from the remote (gh pr view, git ls-remote).
---
1. Read the value back from the remote first:
   `gh pr view <n> --json headRefOid,mergeable` or `git ls-remote origin <ref>`.
2. State it with its source ("read back from the remote").
3. Never send a SHA or merge state in the same batch as the push that
   produced it.
