---
name: sdlc
description: "An AI-native SDLC for a repo — six stages (Plan, Design, Build, Test, Deploy, Maintain), the artifact each produces, and the gate each must pass. Use before starting any feature, when asked \"what stage are we in\", when asked to write the intent/spec/plan, or before opening a PR. Pairs with sdlc-jev, which screens each artifact against its gate before the human looks."
---

# sdlc — an AI-native SDLC

Encodes Anthropic's guide ["The AI-native SDLC playbook"](https://claude.com/blog/the-ai-native-sdlc-playbook)
(2026-08-21) as a repo-local skill. The guide is a document; this file is its
executable form.

The premise: agents make writing code cheap, so the bottleneck moves to **deciding
what to build and proving it works**. This process puts a named artifact and a human
gate in front of each of those decisions, and keeps the audit trail in git.

Naming: if your setup already uses "playbook" for something else (a Claude Code
configuration directory, for instance), call this **the SDLC** or **the sdlc skill** —
never "the playbook".

## Roles, solo edition

The guide assumes product owner, engineer, tech lead, policy owner, release manager.
A solo operator has one human and one or more agents:

| Guide role | Here |
|---|---|
| originator / product owner | the human |
| engineer | the agent working in a worktree |
| tech lead / architect / policy owner / release manager | the human |
| reviewer | a second agent (see the `whetstone` skill) plus the human |

Every gate below therefore means: **the human says yes**, recorded in git — a commit,
a PR approval, or an `Approved:` line in the artifact.

## The six stages

### 1. Plan — `intent.md`

- Human brainstorms with the agent; the result is written as `intent.md` in the
  human's own terms: problem, proposed outcome, affected users and systems,
  constraints, open questions.
- State the **problem separately from the solution**. An intent that opens with an
  implementation has skipped the stage.
- Lives at the repo root while it is current; superseded intents move to `history/`
  (see the `living-docs` skill).
- **Gate:** human approves before Design starts. Approval = a commit of `intent.md`
  carrying an `Approved:` line, or a PR approval.

### 2. Design — `spec.md`

- One session turns `intent.md` into `spec.md`: requirements and design together,
  constrained by whatever conventions the repo already documents.
- Areas of concern are flagged inline as `> CONCERN:` blocks and resolved before Build.
- `spec.md` pairs with `intent.md`: what was asked, and what was decided.
- A spec that deliberately covers **less** than the intent is fine — say so explicitly
  and name what was deferred. Silent narrowing is the failure mode.
- **Gate:** human reviews spec against intent. Accepting the spec starts Build.

### 3. Build — `plan.md`, then code

- Start in **plan mode**. Produce `plan.md`: the files that change, the order of work,
  and **the proof tests**. The human interrogates and approves it before any code
  is written.
- If the implementation departs from the plan, update `plan.md` in the same commit.
- All work on a `<agent>/<description>` branch in a worktree — never on the default
  branch.
- `CLAUDE.md` at the repo root holds conventions, commands, architecture, and common
  mistakes. Rule: **a mistake made twice becomes a `CLAUDE.md` entry.**
- Skills in `.claude/skills/` are policy; hooks in `.claude/settings.json` are
  guardrails (protected paths, formatters, no credentials in diffs). Hooks stay fast
  and scoped to the changed file.
- Parallel work: one worktree per session; subagents for scoped jobs; repeated jobs
  packaged as `.claude/agents/<name>.md` with a tool allowlist.
- **Gate:** human approves `plan.md`. Routine changes: a nod. Higher-risk: explicitly.

### 4. Test — proof in the session report

- Definition of done includes verification output: a test log, build output, or
  screenshot, pasted into the session report and the PR.
- Targets are **quantifiable** ("all tests in `test/x.sh` pass"), never "looks good".
  This is the single most-violated rule in the whole process.
- A verifier subagent runs a final fresh check before the human sees the work.
- During bug fixes, a hook blocks edits to test files.
- Evals: `evals/` holds real tasks with expected outcomes; CI reruns them whenever
  `CLAUDE.md`, `.claude/skills/`, or hooks change. A change that drops the pass rate
  needs review before merge. **Every incident becomes a permanent eval.**

### 5. Deploy — `REVIEW.md` and the gate

- `REVIEW.md` defines the review passes (Bugs, Security, Compliance), severity
  thresholds, and exclusions. Every PR gets the same passes.
- Review is run by a second agent (see `whetstone`) and by `/code-review`; findings
  ranked by severity; **the writing agent never approves its own PR.**
- Findings that repeat feed back into `CLAUDE.md`.
- Approval hooks: a hook may `ask` and pause until the human approves — used for
  production deploys and protected paths. The agent may act up to the production
  gate and cannot pass it.
- Headless `claude -p` in CI for triage, changelogs, and review-comment fixes; output
  arrives as a PR, never as a direct write to the default branch.
- Per-environment autonomy: dev free, staging middle, prod gated.

### 6. Maintain — close the loop

- **Detection is deterministic.** A script watches metrics against `bands.yaml`
  (1 sigma log, 2 sigma diagnose, 3 sigma propose). No model in the detector.
- On a breach, a headless agent diagnoses and writes a new `intent.md` — back to
  stage 1. Small fixes arrive as PRs through the review gate.
- Runbooks the agent may invoke are pre-approved and version controlled; every
  invocation is logged.
- Post-mortems go to `history/lessons.md`.

## Governance principles

1. Human judgment stays above the loop; the agent acts inside gates.
2. Artifacts are the audit trail: author, timestamp, approval, all in git.
3. Controls scale with throughput: a faster build needs faster review and test — by
   automation, not by policy alone.
4. Deterministic detection, tiered response.
5. Separation of duties: the agent that wrote the code does not approve it.

## Quick reference

| Stage | Artifact | Gate |
|---|---|---|
| Plan | `intent.md` | human approves intent |
| Design | `spec.md` | human accepts spec against intent |
| Build | `plan.md`, code in a worktree | human approves plan before code |
| Test | verification output in the report | quantified target met |
| Deploy | `REVIEW.md`, PR | review passes clean, human approves, hook gates prod |
| Maintain | `bands.yaml`, new `intent.md` | human triages proposals |

## How to use this skill

- Starting a feature: ask "which stage?" If no `intent.md` exists for it, you are at
  stage 1. **Do not write code before `plan.md` is approved.**
- Every artifact carries a header: `Stage`, `Author`, `Created` (YYYY-MM-DD-HH_MM),
  and `Approved:` (who, timestamp) once gated.
- When in doubt which gate applies, stop and ask; that is the gate working.

## Companion: automated pre-gate screening

Each gate above is a **human** decision, and stays one. But the criteria are written
down here in prose — "covers the intent", "targets are quantifiable", "concerns
resolved" — and prose criteria can be screened before the human reads a word.

The **`sdlc-jev`** skill does that: it turns each gate's written criteria into typed
judgments with calibrated probabilities, so the human arrives at the gate already
knowing where to look. It reports; it never approves. See
[`../sdlc-jev/SKILL.md`](../sdlc-jev/SKILL.md).
