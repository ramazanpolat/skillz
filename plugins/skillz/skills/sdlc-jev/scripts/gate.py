#!/usr/bin/env python3
"""Pre-gate screening for the `sdlc` skill, using TypeSafe System One (Jev).

Reads the gate criteria from gates.json, asks all of one gate's questions in a
single parallel request, applies the thresholds, and prints a report.

It never approves anything. The SDLC gate is a human decision; this tells the
human where to look before they make it.

    gate.py design                          # uses ./intent.md and ./spec.md
    gate.py build --repo ~/src/thing
    gate.py test  --input report_md=SESSION.md
    gate.py deploy --input findings=review-output.txt
    gate.py design --json                   # machine-readable, for CI

Exit codes:  0 pass    1 review    2 blocked    3 usage/config error
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
except ImportError:
    sys.exit("typesafe-sdk is not installed.  pip install typesafe-sdk  (needs Python >= 3.10)")

HERE = Path(__file__).resolve().parent
DEFAULT_GATES = HERE.parent / "gates.json"

BUILDERS = {"noul": Noul, "choice": Choice, "score": Score}
OPS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


# --- answers ---------------------------------------------------------------

def value_of(response, qid, qtype):
    """The single number or label a rule compares against."""
    if qtype == "noul":
        return response.nouls[qid].noul
    if qtype == "score":
        return response.scores[qid].score
    return response.choices[qid].choice


def confidence_of(response, qid, qtype):
    """Noul has no separate confidence -- it is a probability already."""
    if qtype == "noul":
        return None
    box = response.scores if qtype == "score" else response.choices
    return box[qid].confidence


def legend_of(score_answer):
    """legend may arrive as a dict keyed by level or as a list."""
    items = score_answer.legend.items() if isinstance(score_answer.legend, dict) \
        else enumerate(score_answer.legend)
    return sorted((int(k), str(v)) for k, v in items)


# --- rules -----------------------------------------------------------------

def evaluate(rule, response, types):
    """'qid op value' -> bool.  'in' takes a comma-separated list."""
    parts = rule.split(None, 2)
    if len(parts) != 3:
        raise ValueError(f"malformed rule: {rule!r}")
    qid, op, rhs = parts
    if qid not in types:
        raise ValueError(f"rule {rule!r} names unknown question {qid!r}")

    left = value_of(response, qid, types[qid])
    if op == "in":
        return str(left) in {s.strip() for s in rhs.split(",")}
    if op not in OPS:
        raise ValueError(f"rule {rule!r} uses unknown operator {op!r}")
    try:
        right = float(rhs)
    except ValueError:
        return OPS[op](str(left), rhs)
    return OPS[op](float(left), right)


# --- rendering -------------------------------------------------------------

def bar(p, width=28):
    return "#" * round(max(0.0, min(1.0, p)) * width)


def render(gate_name, gate, response, types, blockers, status, detail):
    print(f"\n=== SDLC stage {gate['stage']} :: {gate['title']} ===\n")

    for qid, qtype in types.items():
        if qtype != "noul":
            continue
        p = response.nouls[qid].noul
        print(f"  {qid:26} {p:5.2f}  {bar(p)}")

    for qid, qtype in types.items():
        if qtype != "choice":
            continue
        a = response.choices[qid]
        print(f"\n  {qid:26} {a.choice}   (confidence {a.confidence:.2f})")
        for opt, p in sorted(a.probabilities.items(), key=lambda kv: -kv[1]):
            if p >= 0.01:
                print(f"  {'':28} {opt:16} {p:5.2f} {bar(p, 18)}")

    for qid, qtype in types.items():
        if qtype != "score":
            continue
        a = response.scores[qid]
        levels = legend_of(a)
        top = max(l for l, _ in levels)
        print(f"\n  {qid:26} {a.score:.2f} / {top}   (confidence {a.confidence:.2f})")
        for lvl, text in levels:
            mark = "<--" if abs(a.score - lvl) < 0.5 else "   "
            print(f"  {'':28} {lvl}  {text[:56]:56} {mark}")

    print("\n  " + "-" * 62)
    if status == "blocked":
        print("  BLOCKED -- resolve before taking this to the gate:")
        for b in blockers:
            print(f"    - {b}")
    elif status == "pass":
        print(f"  PASS -- screening found nothing. {detail}")
        print("  The gate itself is still the human's call.")
    else:
        print(f"  REVIEW -- {detail}")

    u = response.usage
    print(f"\n  {u.input_tokens} input tokens, {len(types)} questions, "
          f"${u.input_tokens * 0.042 / 1e6:.6f}\n")


# --- main ------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="SDLC pre-gate screening via TypeSafe Jev.")
    ap.add_argument("gate", help="which gate to screen")
    ap.add_argument("--repo", default=".", help="repo root (default: cwd)")
    ap.add_argument("--gates", default=str(DEFAULT_GATES), help="path to gates.json")
    ap.add_argument("--input", action="append", default=[], metavar="KEY=PATH",
                    help="supply or override a state input")
    ap.add_argument("--model", help="override the model in gates.json")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a report")
    args = ap.parse_args()

    if not os.environ.get("TYPESAFE_API_KEY"):
        sys.exit("TYPESAFE_API_KEY is not set.  Create one at https://console.typesafe.ai/")

    try:
        config = json.loads(Path(args.gates).read_text())
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"cannot read {args.gates}: {e}")

    gates = config["gates"]
    if args.gate not in gates:
        sys.exit(f"unknown gate {args.gate!r}. Available: {', '.join(gates)}")
    gate = gates[args.gate]

    # Resolve state inputs: gates.json defaults, then --input overrides.
    repo = Path(args.repo)
    paths = dict(gate["inputs"])
    for pair in args.input:
        if "=" not in pair:
            sys.exit(f"--input expects KEY=PATH, got {pair!r}")
        key, _, val = pair.partition("=")
        paths[key] = val

    state = {}
    for key, rel in paths.items():
        if rel is None:
            sys.exit(f"gate {args.gate!r} needs --input {key}=<path>")
        path = Path(rel)
        if not path.is_absolute():
            path = repo / path
        if not path.exists():
            sys.exit(f"missing input for {key}: {path}")
        state[key] = path.read_text()

    types = {qid: spec["type"] for qid, spec in gate["questions"].items()}
    questions = {}
    for qid, spec in gate["questions"].items():
        kwargs = {"instructions": spec["instructions"]}
        if "criteria" in spec:
            kwargs["criteria"] = spec["criteria"]
        questions[qid] = BUILDERS[spec["type"]](**kwargs)

    with TypeSafeClient() as client:
        response = client.system_one(
            state=state,
            questions=questions,
            model=args.model or config.get("model", "jev-latest"),
        )

    try:
        blockers = [r["say"] for r in gate.get("blockers", [])
                    if evaluate(r["when"], response, types)]
    except ValueError as e:
        sys.exit(f"gates.json: {e}")

    rule = gate.get("pass", {})
    qid = rule.get("score")
    status, detail = "review", "no pass rule configured"
    if qid:
        score = response.scores[qid].score
        conf = response.scores[qid].confidence
        floor, ceil = rule.get("min"), rule.get("max")
        ok = (floor is None or score >= floor) and (ceil is None or score <= ceil)
        if conf < rule.get("min_confidence", 0.0):
            status = "review"
            detail = (f"{qid} {score:.2f} but confidence {conf:.2f} is below the "
                      f"{rule['min_confidence']:.2f} bar -- the judgment is not settled.")
        elif ok:
            status, detail = "pass", f"{qid} {score:.2f} (confidence {conf:.2f})."
        else:
            bound = f">= {floor}" if floor is not None else f"<= {ceil}"
            status = "review"
            detail = f"{qid} {score:.2f} does not meet {bound} (confidence {conf:.2f})."

    if blockers:
        status = "blocked"

    if args.json:
        print(json.dumps({
            "gate": args.gate,
            "stage": gate["stage"],
            "status": status,
            "detail": detail,
            "blockers": blockers,
            "answers": {
                qid: {
                    "type": t,
                    "value": value_of(response, qid, t),
                    "confidence": confidence_of(response, qid, t),
                }
                for qid, t in types.items()
            },
            "usage": {"input_tokens": response.usage.input_tokens},
        }, indent=2))
    else:
        render(args.gate, gate, response, types, blockers, status, detail)

    return {"pass": 0, "review": 1, "blocked": 2}[status]


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
