---
name: sdlc-jev
description: "Screen an SDLC artifact against its gate criteria before a human reviews it, using TypeSafe System One (Jev) — typed judgments with calibrated probabilities instead of a reviewer's prose. Use when asked to check whether intent.md / spec.md / plan.md / a test report / a review is ready for its gate, when asked to run the SDLC pre-gate, or before taking any SDLC artifact to its human gate. Companion to the sdlc skill; it reports and never approves."
---

# sdlc-jev — screening the gate before the human reaches it

The [`sdlc`](../sdlc/SKILL.md) skill puts a human gate in front of every stage. This
skill runs *before* that gate, turning each stage's written criteria into typed
judgments so the human arrives already knowing where to look.

**It never approves anything.** The SDLC's first governance principle is that human
judgment stays above the loop, and its fifth is separation of duties. A screening
pass that could approve would break both. This one reports; the human decides.

## Why a System One model and not an LLM

The gate criteria are prose — *"covers the intent"*, *"targets are quantifiable,
never 'looks good'"*, *"concerns resolved"*. No regex checks those. The usual
alternative is asking a chat model, which returns a confident paragraph you then have
to re-judge yourself. That is not screening; it is a second opinion you did not ask for.

[TypeSafe](https://docs.typesafe.ai)'s System One models — **Jev** is the current one —
return typed answers and calibrated probabilities instead of text. A gate criterion
becomes a question with a defined answer set, and the answer arrives as a number your
policy can act on.

Three properties make this fit the SDLC specifically:

- **Every rule stays visible.** The criterion lives in `sdlc/SKILL.md` as prose for
  humans and in `gates.json` as a question. Change the rule, change one question.
- **Uncertainty is reported, not hidden.** When a judgment is genuinely ambiguous the
  confidence says so, and the screening returns `review` rather than a verdict.
- **It is cheap enough to be routine.** A full Design screening over two real ~5k-word
  documents costs about **$0.0008**. You can run this on every commit.

## Setup

```bash
pip install typesafe-sdk          # needs Python >= 3.10
export TYPESAFE_API_KEY=...       # create one at https://console.typesafe.ai/
```

Keep the key in a secret store, not in the repo. In CI, use the platform's secret
mechanism; `gate.py` reads only the environment variable.

## Use

```bash
scripts/gate.py design                        # reads ./intent.md and ./spec.md
scripts/gate.py plan   --repo ~/src/thing
scripts/gate.py build
scripts/gate.py test   --input report_md=SESSION.md
scripts/gate.py deploy --input findings=review-output.txt
scripts/gate.py design --json                 # machine-readable, for CI
```

Exit codes: `0` pass · `1` review · `2` blocked · `3` usage error. A CI job can gate
on `2` alone and let `1` through with a comment.

## The five gates

Each mirrors the written criteria of one SDLC stage. Stage 6 (Maintain) has **no**
gate here on purpose — its detector must stay deterministic (`bands.yaml` sigma bands,
no model). Jev belongs in the *diagnose* step after a breach, writing the next
`intent.md`, never in detection.

| Gate | Reads | Screens for |
|---|---|---|
| `plan` | `intent.md` | Problem stated apart from the solution; constraints falsifiable; listed open questions actually still open |
| `design` | `intent.md`, `spec.md` | Coverage of the intent; **silent** narrowing; unresolved `> CONCERN:` blocks; scope drift; target quantifiability |
| `build` | `plan.md`, `spec.md` | Files named; **proof tests named**; work ordered; plan follows the spec; risk level |
| `test` | a report | Real output pasted rather than described; claims matching that output; undisclosed failures; **quantified targets** |
| `deploy` | `REVIEW.md`, findings | Every defined pass actually run; unresolved findings; **self-approval** (principle 5); highest severity |

## Editing the criteria

Everything lives in [`gates.json`](gates.json) — questions, answer definitions, and
thresholds. `gate.py` contains no criteria of its own.

A blocker is a rule `"<question> <op> <value>"`, with `op` one of `< <= > >= == != in`
(`in` takes a comma list):

```json
{ "when": "target_quantifiability < 2.0",
  "say": "verification targets are not quantifiable enough" }
```

The pass rule names one Score question, a bound, and a confidence floor:

```json
{ "score": "readiness", "min": 2.5, "min_confidence": 0.6 }
```

When confidence falls below the floor, the result is `review` regardless of the
score — an unsettled judgment is not a verdict.

## Reading the output

- **Noul** is a probability of *yes*, with no separate confidence. `0.5` means "as
  likely yes as no", **not** "medium".
- **Choice** and **Score** carry a `confidence` that measures how concentrated the
  distribution is — not whether the answer is correct, and not permission to act.
- A near-tie with low confidence is the model working correctly. In one real run,
  `needs_attention` split 0.41 architecture / 0.40 dependencies at confidence 0.27.
  The honest reading is "these are genuinely comparable", not "architecture wins".

## Calibrate before you trust it

The thresholds shipped in `gates.json` are **starting points, not measurements**.
TypeSafe's own documentation is explicit that cookbook thresholds are examples to
evaluate. Typed output guarantees the interface, not the truth.

Before letting this block anything:

1. Collect artifacts you already know the verdict for — specs that were ready, specs
   that were not — into the repo's `evals/` directory. The `sdlc` skill already calls
   for `evals/`; this is a good first inhabitant.
2. Run each gate over them and compare against what you know.
3. Move the thresholds until the false blocks and the misses are both acceptable.
4. Re-run after any model change. Pin a version (`"model": "jev-1.13.0"`) rather than
   `jev-latest` so a model update cannot silently move your gates.

A worked example of why this matters: an early version of the `design` gate blocked
on `covers_intent < 0.75` alone. Run against a real spec that *deliberately* scoped
down to a v0, it blocked — correctly detecting less coverage, wrongly calling it a
defect. The fix was a second question, `narrowing_is_explicit`, separating "covers
less" from "covers less without saying so". **A false block usually means a missing
distinction, not a wrong threshold.**

## What this does not do

- It does not approve a gate, and must not be wired to.
- It does not read code. It screens the artifacts the SDLC requires — intent, spec,
  plan, report, review. Code review is [`whetstone`](../whetstone/SKILL.md) and
  `/code-review`.
- It does not replace the reviewer. A clean screening means "nothing in the written
  criteria tripped", which is a much narrower claim than "this is good".
- It is text-only and English-first, like the model underneath it.

## Files

```text
sdlc-jev/
├── SKILL.md
├── gates.json           # all criteria and thresholds; edit this
└── scripts/
    └── gate.py          # runner: reads gates.json, one parallel request per gate
```
