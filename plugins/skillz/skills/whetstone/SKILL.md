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
| Findings | `pulls/N/reviews` (review **body**) **and** `pulls/N/comments` (inline) |
| "Didn't find any major issues" | `issues/N/comments` — a plain issue comment |

Query both finding endpoints every round. A round whose feedback sits in the review
body rather than inline comments will otherwise look empty, and the loop will stop
with findings unaddressed.

A watcher looking only at reviews **times out on a clean round** and looks like
nothing happened.

Two traps make naive polling wrong, and both have bitten:

- **`commit_id` is not a freshness signal.** GitHub *re-anchors* existing review
  comments onto the new head when a file changes, so old findings reappear carrying
  the current SHA. Filtering by `commit_id == head` returns stale comments as if they
  were this round's.
- **A stale clean verdict is still sitting there.** After any earlier clean round,
  "didn't find any major issues" stays in the thread forever. Matching on the text
  alone will report clean the instant you re-request, before the new review runs —
  and merge on it.

So: **baseline the ids before re-requesting, and require the verdict to name the
current head.** Comment ids increase monotonically, which is all the ordering needed.

**Paginate.** These threads outgrow one page fast — a single campaign reached 32
inline comments, past the default 30. And `--paginate --jq` runs the filter *per
page*, so `[.[].id] | max` yields one maximum per page rather than one for the
thread. `--slurp` aggregates, but it is rejected together with `--jq`, so slurp and
pipe to a separate `jq`.

```bash
R=OWNER/REPO N=42
# every query below: --paginate --slurp, piped to jq. .[][] flattens page,item.
api() { gh api --paginate --slurp "$1"; }

# 1. BEFORE commenting "@codex review" — record where the thread stands
BASE_C=$(api "repos/$R/pulls/$N/comments"  | jq '[.[][].id] | max // 0')
BASE_R=$(api "repos/$R/pulls/$N/reviews"   | jq '[.[][].id] | max // 0')
BASE_V=$(api "repos/$R/issues/$N/comments" | jq '[.[][].id] | max // 0')

# 2. AFTER the review lands — findings from BOTH endpoints, only the new ones.
#    Review bodies carry findings too; inline comments are not the whole round.
api "repos/$R/pulls/$N/reviews" \
  | jq -r --argjson b "$BASE_R" '.[][] | select(.id > $b) | select((.body//"")!="")
      | "REVIEW \(.id)\n\(.body)\n"'
api "repos/$R/pulls/$N/comments" \
  | jq -r --argjson b "$BASE_C" '.[][] | select(.id > $b)
      | "INLINE \(.id) \(.path):\(.line)\n\(.body)\n"'

# 3. Clean only if a NEW verdict names the CURRENT head (body abbreviates to 10 chars)
HEAD=$(gh api "repos/$R/pulls/$N" --jq .head.sha)
api "repos/$R/issues/$N/comments" \
  | jq -r --argjson b "$BASE_V" --arg h "${HEAD:0:10}" '
      [ .[][] | select(.id > $b)
              | select(.user.login | test("codex";"i"))
              | select(.body | contains($h))
              | select(.body | test("find any major issues")) ] as $v
      | if ($v|length) > 0 then "CLEAN for \($h)" else "not clean yet" end'
```

Verified against real threads: the head-correlated check reports CLEAN on a PR whose
verdict names that SHA and `not clean yet` on PRs with open findings; and with
pagination forced (`?per_page=2`), the slurped form returns one maximum where the
`--jq` form returned six.

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

- The **Codex GitHub app** (`chatgpt-codex-connector`) installed on the account that
  owns the repo.

  There is no single command that confirms this for every account type, so do not
  treat a failed query as "not installed":

  - **Org repo, and you hold `admin:org`** — this works:
    `gh api /orgs/ORG/installations --jq '.installations[].app_slug'`
  - **Personal repo, or no `admin:org`** — it does not. The org endpoint returns 404
    for a user account, and `/user/installations` returns 403 for a normal `gh` token
    ("must authenticate with an access token authorized to a GitHub App"). Check
    `github.com/settings/installations` in a browser, or simply open the PR, request
    the review, and see whether the app answers within a few minutes.
- Use the app, not the local CLI. `codex exec` buffers its output and has produced
  nothing in 45 minutes where the app answered the same question in about two.
- Work on a branch in its own worktree; never commit to the default branch directly.
