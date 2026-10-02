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

1. **Open the PR** with `@codex review` as the first line of the body. This triggers
   the first review immediately, so **the first round has no baseline to take** — the
   PR number does not exist until the PR does. Treat every id as new for round one
   (`BASE_*=0`); anything else races the reviewer and silently swallows the round.
2. **Wait** for the review (see *Watching for the review*) — against a deadline, not
   indefinitely (see *Deadline, quota and the fallback reviewer*).
3. **Triage every finding.** Confirm or refute each against the code — do not accept
   on authority, and do not dismiss on ego.
4. **Fix**, verifying each fix empirically (see *Verification*).
5. **Commit and push, and confirm the remote head moved.** The reviewer reads the
   remote, not your worktree. Skip this and the next round re-reads the unchanged
   head: at best it repeats the findings you just fixed, at worst it returns clean
   and the merge criterion is satisfied by code that never left your machine — the
   head-correlated check under *Watching for the review* asks GitHub for `pulls/N`
   `head.sha`, which is the *remote* head, so it will happily confirm a stale commit.
6. **Baseline, then reply.** Capture the ids **before** posting, because the reply is
   what re-triggers the review. Name what was valid, what was refuted and with what
   evidence, and what was a deliberate non-fix. End with `@codex review`.
7. **Repeat** until a round returns clean.
8. **Merge**, remove the worktree, delete the branch.

The ordering in steps 1 and 6 is the whole trick: **a baseline is only valid if it is
taken before the request that it is meant to bound.** Take it after, and the round's
own ids land inside the baseline and are then filtered out by `id > $b` — the loop
waits forever for findings that already arrived.

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
| Findings | `pulls/N/reviews` (review **body**) **and** `pulls/N/comments` (inline) — and **no** issue comment |
| "Didn't find any major issues" | `issues/N/comments` — a plain issue comment |
| Clean, silently | a 👍 (`+1`) **reaction** on the request itself — the `@codex review` comment, or the PR body in round one — with no comment anywhere |
| Quota exhausted | `issues/N/comments` — "You have reached your Codex usage limits for code reviews" |

Query all of them every round. A round whose feedback sits in the review body rather
than inline comments will otherwise look empty, and the loop will stop with findings
unaddressed.

Each blind spot has bitten, and each produced a confident wrong story:

- A watcher looking only at reviews **times out on a clean round** and looks like
  nothing happened.
- A watcher looking only at issue comments **sees silence on a round with findings**
  and reports "waiting on Codex" while the findings sit on the head — for 50 minutes,
  in one case, with a secrets-leak finding among them.
- The app's own reply to a request says "if Codex has suggestions, it will comment;
  otherwise it will react with 👍". A watcher that reads no reactions cannot see that
  kind of clean pass at all.

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

# 1. FIRST ROUND (PR just opened with the mention): there is nothing to bound yet.
BASE_C=0 BASE_R=0 BASE_V=0

# 1'. EVERY LATER ROUND: baseline BEFORE posting the reply that re-triggers the
#     review. Taken afterwards, the round's own ids fall inside the baseline and
#     `id > $b` hides them.
BASE_C=$(api "repos/$R/pulls/$N/comments"  | jq '[.[][].id] | max // 0')
BASE_R=$(api "repos/$R/pulls/$N/reviews"   | jq '[.[][].id] | max // 0')
BASE_V=$(api "repos/$R/issues/$N/comments" | jq '[.[][].id] | max // 0')

# 2. AFTER the review lands — findings from BOTH endpoints, only the new ones.
#    Review bodies carry findings too; inline comments are not the whole round.
api "repos/$R/pulls/$N/reviews" \
  | jq -r --argjson b "$BASE_R" '.[][] | select(.id > $b) | select((.body//"")!="")
      | "REVIEW \(.id)\n\(.body)\n"'
# .line is null once a comment goes outdated — fall back to original_line.
api "repos/$R/pulls/$N/comments" \
  | jq -r --argjson b "$BASE_C" '.[][] | select(.id > $b)
      | "INLINE \(.id) \(.path):\(.line // .original_line // "?")\n\(.body)\n"'

# 3. Clean only if a NEW verdict from the APP names the CURRENT head.
#    Identify by performed_via_github_app.slug, never by a login substring: on a
#    public PR anyone can be called *codex* and post the SHA plus the magic phrase,
#    and a substring match would hand them your merge criterion. That field is
#    stamped by GitHub when an app posts, so a human commenter cannot forge it.
#    (The body abbreviates the SHA to 10 characters.)
HEAD=$(gh api "repos/$R/pulls/$N" --jq .head.sha)
api "repos/$R/issues/$N/comments" \
  | jq -r --argjson b "$BASE_V" --arg h "${HEAD:0:10}" '
      [ .[][] | select(.id > $b)
              | select(.performed_via_github_app.slug == "chatgpt-codex-connector")
              | select(.body | contains($h))
              | select(.body | test("find any major issues")) ] as $v
      | if ($v|length) > 0 then "CLEAN for \($h)" else "not clean yet" end'
```

The 👍 channel carries no SHA, so correlate it through the request instead: record the
request's id and the head at the moment you post it, and count the reaction only if
the head has not moved since. Identify the reactor by its exact login,
`chatgpt-codex-connector[bot]`. GitHub usernames cannot contain brackets, so a person
cannot hold that login. Do **not** also filter on `user.type == "Bot"`: on a
reaction the app is reported as `"User"`, and that filter silently drops every clean
pass sent this way. Measured on a real 👍 from the app.

```bash
# REQ = id of the `@codex review` comment you posted this round, REQ_HEAD = head then.
# Round one: the request is the PR body, so read issues/$N/reactions instead.
[ "$(gh api "repos/$R/pulls/$N" --jq .head.sha)" = "$REQ_HEAD" ] &&
api "repos/$R/issues/comments/$REQ/reactions" \
  | jq -r '[ .[][] | select(.content == "+1")
              | select(.user.login == "chatgpt-codex-connector[bot]") ]
      | if length > 0 then "CLEAN (reaction) for the requested head" else "no reaction" end'
```

Verified against real threads: the head-correlated check reports CLEAN on a PR whose
verdict names that SHA and `not clean yet` on PRs with open findings; and with
pagination forced (`?per_page=2`), the slurped form returns one maximum where the
`--jq` form returned six.

## Deadline, quota and the fallback reviewer

Rounds answer in about **2–7 minutes**. The reviewer is also quota-limited, and a
loop that cannot tell silence from latency stalls every pipeline behind it.

- **"Waiting on Codex" is never a status by itself.** Report it only with: when the
  request was posted and how long ago, the result of checking every channel in the
  table above since the baseline, and whether the newest reviewed commit is the head.
- **Check for the quota reply first.** A new app comment matching `usage limits for
  code reviews` ends the round immediately: no review is coming for this request, and
  re-requesting will not change that until the quota resets.

  ```bash
  api "repos/$R/issues/$N/comments" \
    | jq -r --argjson b "$BASE_V" '.[][] | select(.id > $b)
        | select(.performed_via_github_app.slug == "chatgpt-codex-connector")
        | select(.body | test("usage limits for code reviews"))
        | "QUOTA \(.created_at)"'
  ```
- **Deadline: 20 minutes.** Nothing on any channel for the current head after 20
  minutes is **likely quota**, even with no quota reply. Say so to the user in those
  words and move to the fallback. Do not keep polling in silence.

**The fallback reviewer** is a second agent from a different vendor than the author,
run locally on the same diff with the same PR body. For example, Antigravity with a
Gemini model, reviewing read-only:

```bash
S=$(mktemp -d)                      # the reviewer runs HERE, never in a checkout
{ cat pr-body.md; echo; echo 'Review this diff. List findings, or end with the line VERDICT: clean'; \
  git diff "origin/$BASE...HEAD"; } > "$S/prompt.txt"
HEAD_BEFORE=$(git rev-parse HEAD)
(cd "$S" && agy --model gemini-3.1-pro-high --print-timeout 20m --mode plan --print="$(cat prompt.txt)")
[ "$(git rev-parse HEAD)" = "$HEAD_BEFORE" ] && [ -z "$(git status --porcelain)" ] || echo "the reviewer changed the checkout"
```

Put `--print=` last and attach the prompt with `=`: a bare `--print` swallows the next
token as its prompt. Embed the diff and launch from an empty scratch directory:
`--mode plan` does not keep a reviewer out of your repositories, and one run went
looking for the PR on its own and `git checkout`-ed it in the user's primary checkout.
Handle its findings exactly like Codex's.

A fallback verdict is weaker than the loop's merge criterion, and the user decides
whether it is enough:

- **Report it as what it is.** "Clean from the fallback reviewer (Antigravity,
  gemini-3.1-pro-high) on `<sha>`; Codex unavailable (quota since HH:MM)". Never
  "clean" on its own.
- **Do not merge on a fallback verdict unless the user says so.** Offer the choice:
  merge now, or re-request `@codex review` when the quota resets.
- **Never fall back to the authoring agent reviewing itself.** "The reviewer is not
  the author" is the property this whole loop exists for. A same-vendor subagent is
  the last resort, and if you use one, say so.

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
