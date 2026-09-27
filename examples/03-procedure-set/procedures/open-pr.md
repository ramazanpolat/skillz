---
name: open-pr
title: Opening a pull request
mode: auto
fires_on: [bash, user_prompt]
covers: Creating a pull request now: running gh pr create, or the user asks to open one.
excludes: Viewing, listing or discussing existing PRs; the user saying not to open one.
---
1. Request `@codex review` once, in the PR body, unless Codex answered with its
   usage-limit message today; then say in the body which reviewer is the review
   of record instead.
2. Never re-request Codex on fix rounds.
3. End the body with the attribution line the session requires.
4. After creating it, report the head only as read back:
   `gh pr view <n> --json headRefOid,mergeable`.
