---
name: whetstone
description: "Adversarial cross-agent review loop — open a PR, have a second agent (Codex) review it, fix every finding, re-request, and repeat until a round returns clean, then merge. Use when the user says \"whetstone\", \"run it over the whetstone\", \"sharpen this PR\", or asks to review-and-fix a branch until the reviewer is clean. Also use when landing any non-trivial change that is not merely mechanical."
---

# whetstone

Sharpen a change against a second agent until no burr remains.

One agent writes, another attacks, the writer fixes, and the cycle repeats until a
full round lands nothing. The merge criterion is not "looks fine" — it is **a review
round that returns zero findings on the current head commit**.

## Why this exists

Measured over a single day's campaign on one Node/SQL codebase: **20 review rounds,
32 findings, every one a real defect.** The distribution is the interesting part:

- Six rounds found defects in the fix written for the *previous* round.
- One found a claim the author had asserted as fact that was simply false.
- One found an error being swallowed by code written *to stop swallowing errors*.
- Three separate rounds found a pattern fixed in one module and not its siblings.

The single most valuable property is that **the reviewer is not the author**. Nearly
every finding was in something the author had just convinced themselves was correct.

## The loop

```
open PR ──> @codex review ──> fix ALL findings ──> re-request
                ^                                       |
                └──────────── not clean ────────────────┘
                                  |
                                clean
                                  v
                                merge
```

1. **Open the PR** with `@codex review` as the first line of the body.
2. **Wait** for the review (see *Watching for the review*).
3. **Triage every finding.** Confirm or refute each against the code — do not accept
   on authority, and do not dismiss on ego.
4. **Fix**, verifying each fix empirically (see *Verification*).
5. **Reply** naming what was valid, what was refuted and with what evidence, and what
   was a deliberate non-fix. End with `@codex review`.
6. **Repeat** until a round returns clean.
7. **Merge**, remove the worktree, delete the branch.

## Writing the PR body

The mention alone gets a generic review. What produces sharp findings is telling the
reviewer what would count as *wrong*:

- What kind of repo it is, and which file is the contract.
- What the change claims to do.
- **A numbered list of wrong-claim criteria** — the specific things that, if true,
  mean this PR is broken. Write the ones you are least sure of.
- Anything deliberately not done, and why. Unstated omissions read as oversights and
  come back next round.

Naming your own uncertainties is the highest-yield part of the body. Several of the
sharpest findings in the campaign above came from criteria the author volunteered.

## Verification

A finding is not fixed because the code changed. It is fixed when the failure is
reproduced and then shown not to happen.

- **Reproduce first.** Stage the actual broken state — corrupt the file, `chmod 000`
  the store, remove the native binding — and confirm the bad behaviour before fixing.
- **Test both directions.** A guard that never fires and a guard that always fires
  look identical from the happy path. Check that the healthy case stays silent.
- **Prefer real data, and say which you used.** Synthetic fixtures miss what the real
  store contains; real data misses the cases it happens not to contain.
- **Restore what you disturb.** Back up before destructive fixtures, restore after,
  and re-verify the restore.
- **A test that cannot fail is not a test.** A fixture needing `sudo` on a host where
  `sudo` prompts will silently no-op, and the test "passes" while proving nothing.
  Check the precondition actually took effect.

## Watching for the review

The reviewer posts through two different endpoints, and getting this wrong wastes a
cycle:

| What | Where |
|---|---|
| Findings | `pulls/N/reviews` **and** `pulls/N/comments` (inline) |
| "Didn't find any major issues" | `issues/N/comments` — a plain issue comment |

A watcher looking only at reviews **times out on a clean round** and looks like
nothing happened.

**Key on the comment id alone.** GitHub re-anchors existing review comments to the new
head commit when a file changes, so a key of `id+path+commit` makes old comments look
new. Read each comment's `commit_id` to tell a fresh finding from a re-post against an
older commit.

```bash
# every finding, with the commit it was written against
gh api "repos/OWNER/REPO/pulls/N/comments" \
  --jq '.[] | "\(.id) \(.commit_id[0:8]) \(.path):\(.line)\n\(.body)\n"'

# the clean verdict lives here instead
gh api "repos/OWNER/REPO/issues/N/comments" \
  --jq '.[] | select(.user.login | test("codex")) | .body'
```

## Working the findings

- **Fix the class, not the instance.** If one module swallows an error, check them
  all. Three separate rounds went on the same pattern surviving in a sibling.
- **Suspect your own last fix hardest.** It is the least-reviewed code in the diff.
- **Check the layer behind the one you fixed.** Instrumenting a call site does not
  help if the callee catches internally; guarding a write does not help if control
  never reaches the guard.
- **Two findings can pull in opposite directions.** One says report more, another says
  you are now rejecting readable input. Resolve them together, not separately.
- **Refuting is allowed, with evidence.** State the check you ran.
- **A deliberate non-fix is fine — say so in the reply.** Silence reads as an oversight.

## When to stop

Stop on a clean round. But do not read a clean round as proof the code is finished —
on a long campaign it more likely means the remaining defects are beyond what static
review reaches. Say so plainly when reporting.

If rounds keep finding real defects well past the original scope, surface that to the
user as a decision rather than continuing indefinitely. Shipping a demonstrably better
artifact with the remainder tracked is often the better call.

## Prerequisites

- The **Codex GitHub app** (`chatgpt-codex-connector`) installed on the org or user
  account. Verify:
  `gh api /orgs/ORG/installations --jq '.installations[].app_slug'`
- Use the app, not the local CLI. `codex exec` buffers its output and has produced
  nothing in 45 minutes where the app answered the same question in about two.
- Work on a branch in its own worktree; never commit to the default branch directly.
