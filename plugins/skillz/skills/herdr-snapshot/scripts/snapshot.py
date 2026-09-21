#!/usr/bin/env python3
"""Snapshot a herdr session's layout and match every tab to a Kommander playbook task.

Captures every workspace/tab/pane in a herdr session (labels + cwd), then cross-
references each tab's label against every local Kommander playbook install under
~/.claude-playbooks/*/data/tasks/ to work out which playbook + task + resumable
session id was probably running there. The tab-title = task-name convention (a
Kommander/herdr habit: name each tab after the task its agent is working) is the
primary signal; a currently-held task lock's session= id is what makes the tab
resumable later with `resurrect.py`.

Usage:
    snapshot.py save [--session NAME] [--out PATH] [--playbooks-dir DIR]
    snapshot.py save --session default --out ~/.herdr-snapshots/pre-reboot

Writes <out>.json (machine-readable, consumed by resurrect.py) and <out>.md
(human-readable report). Prints the output paths and a one-line summary.

No side effects: this only reads herdr state and playbook task folders. It never
acquires or releases a lock, and never touches herdr beyond `session list` /
`api snapshot`.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import HOME, DEFAULT_PLAYBOOKS_DIR, DEFAULT_SNAPSHOT_DIR, herdr, herdr_json, resolve_session_socket  # noqa: E402

FUZZY_THRESHOLD = 0.3
MAX_CWD_CANDIDATES = 6  # more hits than this means the cwd is too generic (e.g. bare $HOME) to trust


def capture_layout(socket_path):
    """Return {workspaces:[...], tabs_by_ws:{wid:[...]}, panes_by_tab:{tid:[...]}}."""
    snap = herdr_json(["api", "snapshot"], socket_path)["snapshot"]
    tabs_by_ws = {}
    for t in snap["tabs"]:
        tabs_by_ws.setdefault(t["workspace_id"], []).append(t)
    panes_by_tab = {}
    for p in snap["panes"]:
        panes_by_tab.setdefault(p["tab_id"], []).append(p)
    return snap["workspaces"], tabs_by_ws, panes_by_tab


# ---------------------------------------------------------------------------
# playbook / task discovery
# ---------------------------------------------------------------------------

def discover_playbooks(playbooks_dir):
    """Return {playbook_name: {"launcher": alias, "tasks_dir": path}}."""
    out = {}
    if not os.path.isdir(playbooks_dir):
        return out
    for name in sorted(os.listdir(playbooks_dir)):
        root = os.path.join(playbooks_dir, name)
        tasks_dir = os.path.join(root, "data", "tasks")
        if not os.path.isdir(tasks_dir):
            continue
        launcher = name
        manifest = os.path.join(root, ".playbook")
        if os.path.isfile(manifest):
            try:
                text = open(manifest, encoding="utf-8", errors="ignore").read()
                m = re.search(r'^alias\s*=\s*"([^"]+)"', text, re.M)
                if m:
                    launcher = m.group(1)
            except OSError:
                pass
        out[name] = {"launcher": launcher, "tasks_dir": tasks_dir}
    return out


def lock_info(task_path):
    """Return dict(held, session, pid, at) for a task folder, or held=False."""
    lh = os.path.join(task_path, ".lock.held")
    if not os.path.isfile(lh):
        return {"held": False, "session": None, "pid": None, "at": None}
    try:
        content = open(lh, encoding="utf-8", errors="ignore").read()
    except OSError:
        return {"held": False, "session": None, "pid": None, "at": None}
    sm = re.search(r"session=(\S+)", content)
    pm = re.search(r"pid=(\d+)", content)
    am = re.search(r"at=(\S+)", content)
    return {
        "held": True,
        "session": sm.group(1) if sm else None,
        "pid": pm.group(1) if pm else None,
        "at": am.group(1) if am else None,
    }


def load_task_index(playbooks):
    """Return list of task entries across every playbook: one dict per non-hidden folder."""
    tasks = []
    for pb, meta in playbooks.items():
        tdir = meta["tasks_dir"]
        if not os.path.isdir(tdir):
            continue
        for folder in sorted(os.listdir(tdir)):
            if folder.startswith("."):
                continue
            done = folder.startswith("DONE--")
            base = folder[6:] if done else folder
            path = os.path.join(tdir, folder)
            li = lock_info(path)
            tasks.append({
                "playbook": pb,
                "launcher": meta["launcher"],
                "folder": folder,
                "name": base,
                "done": done,
                "path": path,
                **li,
            })
    return tasks


def read_goal(task_path):
    tmd = os.path.join(task_path, "TASK.md")
    if not os.path.isfile(tmd):
        return ""
    try:
        text = open(tmd, encoding="utf-8", errors="ignore").read()
    except OSError:
        return ""
    m = re.search(r"## Goal\s*\n+(.+?)(\n##|\Z)", text, re.S)
    return " ".join(m.group(1).split())[:240] if m else ""


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------

def norm_tokens(s):
    return set(t for t in re.split(r"[^a-z0-9]+", s.lower()) if t)


def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def name_candidates(label, tasks):
    """Exact-then-fuzzy match of a tab label against every task's name (any playbook)."""
    ltok = norm_tokens(label)
    if not ltok or label.strip().isdigit():
        return "untitled", []
    exact = [t for t in tasks if norm_tokens(t["name"]) == ltok]
    if exact:
        return "exact", exact
    scored = sorted(tasks, key=lambda t: -jaccard(ltok, norm_tokens(t["name"])))
    if not scored:
        return "none", []
    top_score = jaccard(ltok, norm_tokens(scored[0]["name"]))
    if top_score < FUZZY_THRESHOLD:
        return "none", []
    cands = [t for t in scored if jaccard(ltok, norm_tokens(t["name"])) >= top_score - 1e-9]
    return "fuzzy", cands


def exact_name_matched_tasks(labels, tasks):
    """(playbook, folder) pairs that are an exact tab-title match for ANY tab in the snapshot.

    These have their own naming home and must never be poached as a cwd-fallback guess for
    a different, unrelated tab (e.g. a task literally named 'npx-cpb' belongs to the tab
    literally titled 'npx-cpb', not to some other tab that merely shares its cwd).
    """
    reserved = set()
    for label in labels:
        ltok = norm_tokens(label)
        if not ltok:
            continue
        for t in tasks:
            if norm_tokens(t["name"]) == ltok:
                reserved.add((t["playbook"], t["folder"]))
    return reserved


def cwd_candidates(cwd, tasks, claimed_sessions, reserved=frozenset()):
    """Fallback: currently-locked, unclaimed, unreserved tasks whose .worktree or TASK.md pin this exact cwd."""
    if not cwd:
        return []
    out = []
    cwd_forms = {cwd}
    if cwd.startswith(HOME + "/"):
        cwd_forms.add("~" + cwd[len(HOME):])
    elif cwd == HOME:
        cwd_forms.add("~")

    for t in tasks:
        if t["done"] or not t["held"] or t["session"] in claimed_sessions:
            continue
        if (t["playbook"], t["folder"]) in reserved:
            continue
        wt_path = os.path.join(t["path"], ".worktree")
        wt_match = False
        if os.path.isfile(wt_path):
            try:
                wtc = open(wt_path, encoding="utf-8", errors="ignore").read().strip()
                wt_match = any(wtc == f or wtc.startswith(f + "/") for f in cwd_forms)
            except OSError:
                pass
        content_match = False
        tmd = os.path.join(t["path"], "TASK.md")
        if os.path.isfile(tmd):
            try:
                text = open(tmd, encoding="utf-8", errors="ignore").read()
                content_match = any(f in text for f in cwd_forms)
            except OSError:
                pass
        if wt_match or content_match:
            out.append((t, wt_match))
    if len(out) > MAX_CWD_CANDIDATES:
        # too many hits to mean anything — cwd is probably a generic/shallow path (bare $HOME,
        # a project parent dir) that shows up incidentally in lots of unrelated TASK.md files
        return []
    # worktree-exact matches are the strongest signal; put them first
    out.sort(key=lambda pair: not pair[1])
    return [t for t, _ in out]


def _resolve_multi(cands, context_note):
    """Given 2+ locked candidates, auto-resolve via lock recency or report as uncertain.

    A task's `.lock.held` "at=" is its last-acquire time; a clean quit leaves the marker in
    place (it does not get deleted), so recency is the same "was this still open at crash
    time" signal whether the candidates came from a name match or a cwd fallback.
    """
    distinct = {(t["playbook"], t["folder"]) for t in cands}
    if len(distinct) == 1:
        return _resume(cands[0], context_note)
    ranked = sorted(cands, key=lambda t: t["at"] or "", reverse=True)
    best, second = ranked[0], ranked[1]
    if (best["at"] or "") > (second["at"] or ""):
        note = (f"{context_note}, {len(distinct)} candidates in different playbooks — picked the most "
                f"recently acquired lock ({best['at']}) over {second['playbook']}/{second['name']} ({second['at']})")
        return _resume(best, note)
    opts = ", ".join(f"{t['playbook']}/{t['name']} ({t['at']})" for t in ranked[:5])
    return {
        "decision": "uncertain",
        "note": f"{context_note}, {len(distinct)} equally-recent candidates: {opts}",
        "candidates": [
            {"playbook": t["playbook"], "launcher": t["launcher"], "task": t["name"],
             "session": t["session"], "goal": read_goal(t["path"])}
            for t in ranked[:5]
        ],
    }


def classify_tab(label, cwd, tasks, claimed_sessions, reserved):
    """Return a decision dict for one tab. Mutates nothing; caller updates claimed_sessions."""
    kind, cands = name_candidates(label, tasks)

    if kind in ("untitled", "none"):
        cwd_cands = cwd_candidates(cwd, tasks, claimed_sessions, reserved)
        if cwd_cands:
            prefix = "untitled tab" if kind == "untitled" else "no name match"
            return _resolve_multi(cwd_cands, f"{prefix}, cwd-matched")
        if kind == "untitled":
            return {"decision": "plain", "note": "untitled tab (herdr default numbering) — no name to match"}
        return {"decision": "plain", "note": "no task name or cwd match found — likely not a Kommander/claude tab"}

    # exact or fuzzy name match
    with_session = [t for t in cands if t["held"] and t["session"]]
    if with_session:
        return _resolve_multi(with_session, f"{kind} name match")

    non_done = [t for t in cands if not t["done"]]
    if non_done:
        t = non_done[0]
        return {
            "decision": "fresh", "playbook": t["playbook"], "launcher": t["launcher"], "task": t["name"],
            "session": None, "note": f"{kind} name match, task exists but is not currently locked — launch and pick from menu",
        }

    # the only name match is DONE/completed — the tab may have been repurposed for something
    # else in the same repo since (this happened for real: a 'claude-playbooks' tab's live task
    # turned out to be an unrelated 'cpb-readme-update' whose TASK.md never once wrote the repo's
    # path, only its name — cwd_candidates() can't see that). This branch's evidence is always
    # weak (we're already past "the name match is stale"), so even a single cwd hit stays
    # 'uncertain' rather than auto-resuming — a *wrong* confident resume is worse than asking.
    done_note = f"only name match is a DONE/completed task ({cands[0]['playbook']}/{cands[0]['folder']})"
    cwd_cands = cwd_candidates(cwd, tasks, claimed_sessions, reserved)
    if cwd_cands:
        opts = ", ".join(f"{t['playbook']}/{t['name']} ({t['session'][:8]}…, {t['at']})" for t in cwd_cands[:5])
        return {
            "decision": "uncertain",
            "note": f"{done_note}; cwd-matched but low-confidence (see skill notes on this failure mode): {opts}",
            "candidates": [
                {"playbook": t["playbook"], "launcher": t["launcher"], "task": t["name"],
                 "session": t["session"], "goal": read_goal(t["path"])}
                for t in cwd_cands[:5]
            ],
        }
    return {"decision": "plain", "note": done_note}


def _resume(t, note):
    return {
        "decision": "resume", "playbook": t["playbook"], "launcher": t["launcher"], "task": t["name"],
        "session": t["session"], "at": t["at"], "pid": t.get("pid"), "note": note,
    }


def build_snapshot(socket_path, playbooks_dir):
    workspaces, tabs_by_ws, panes_by_tab = capture_layout(socket_path)
    playbooks = discover_playbooks(playbooks_dir)
    tasks = load_task_index(playbooks)

    ws_order = sorted(workspaces, key=lambda w: w["number"])
    all_labels = [t["label"] for tabs in tabs_by_ws.values() for t in tabs]
    reserved = exact_name_matched_tasks(all_labels, tasks)
    rows = []
    claimed_sessions = set()

    for w in ws_order:
        wid = w["workspace_id"]
        tabs = sorted(tabs_by_ws.get(wid, []), key=lambda t: t["number"])
        for t in tabs:
            panes = panes_by_tab.get(t["tab_id"], [])
            cwd = panes[0].get("cwd", "") if panes else ""
            pane_id = panes[0]["pane_id"] if panes else None
            row = {
                "ws": w["label"], "ws_num": w["number"], "tab_num": t["number"],
                "label": t["label"], "cwd": cwd, "orig_pane": pane_id,
            }
            decision = classify_tab(t["label"], cwd, tasks, claimed_sessions, reserved)
            row.update(decision)
            if row.get("session"):
                if row["session"] in claimed_sessions:
                    row["decision"] = "duplicate"
                    row["note"] = f"same session already claimed by another tab: {row['note']}"
                    row.pop("playbook", None)
                    row.pop("launcher", None)
                    row.pop("task", None)
                else:
                    claimed_sessions.add(row["session"])
            rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def render_markdown(rows, session_name):
    by_ws = {}
    order = []
    for r in rows:
        key = (r["ws_num"], r["ws"])
        if key not in by_ws:
            by_ws[key] = []
            order.append(key)
        by_ws[key].append(r)

    counts = Counter(r["decision"] for r in rows)
    lines = [
        f"# herdr layout snapshot — session `{session_name}`",
        "",
        f"Generated {datetime.now().strftime('%Y-%m-%d-%H_%M')}. {len(rows)} tabs across {len(order)} workspaces.",
        "",
        f"**Totals:** " + ", ".join(f"{v} {k}" for k, v in counts.most_common()),
        "",
        "Legend: **resume** = `claude --resume <session>` recovers the exact prior conversation "
        "(the SessionStart hook re-attaches the task lock). **fresh** = task identified, no active "
        "lock — launch the playbook and pick the task from its menu. **uncertain** = plausible "
        "candidate(s) exist but confidence is too low to assert automatically — needs a human call. "
        "**duplicate** = same session already assigned to another tab. **plain** = no Kommander task "
        "association found.",
        "",
    ]
    for key in order:
        wnum, wlabel = key
        tabs = sorted(by_ws[key], key=lambda r: r["tab_num"])
        lines.append(f"## {wnum}. {wlabel} ({len(tabs)} tabs)")
        lines.append("")
        lines.append("| Tab | cwd | Decision | Playbook (launcher) | Task | Session | Note |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in tabs:
            cwd = r["cwd"].replace(HOME, "~")
            pb = f"{r.get('playbook','')} (`{r.get('launcher','')}`)" if r.get("playbook") else ""
            sess = (r.get("session") or "")[:8] + ("…" if r.get("session") else "")
            lines.append(f"| `{r['label']}` | {cwd} | **{r['decision']}** | {pb} | {r.get('task','')} | {sess} | {r['note']} |")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_save(args):
    socket_path = resolve_session_socket(args.session) if args.session else os.environ.get("HERDR_SOCKET_PATH")
    if not socket_path:
        print("error: no --session given and $HERDR_SOCKET_PATH is not set (not running inside herdr?)", file=sys.stderr)
        return 1
    session_name = args.session or os.path.basename(os.path.dirname(socket_path)) or "current"

    rows = build_snapshot(socket_path, args.playbooks_dir)

    out_prefix = args.out or os.path.join(DEFAULT_SNAPSHOT_DIR, f"{session_name}-{datetime.now().strftime('%Y-%m-%d-%H_%M')}")
    out_prefix = os.path.expanduser(out_prefix)
    os.makedirs(os.path.dirname(out_prefix) or ".", exist_ok=True)

    json_path = out_prefix + ".json"
    md_path = out_prefix + ".md"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"session": session_name, "generated": datetime.now().isoformat(), "tabs": rows}, f, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(rows, session_name))

    counts = Counter(r["decision"] for r in rows)
    print(f"snapshot: {len(rows)} tabs -> " + ", ".join(f"{v} {k}" for k, v in counts.most_common()))
    print(json_path)
    print(md_path)
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("save", help="capture + match a herdr session's layout")
    ps.add_argument("--session", help="herdr session name (default: $HERDR_SOCKET_PATH, i.e. the calling pane's own session)")
    ps.add_argument("--out", help="output path prefix (writes <out>.json and <out>.md); default: ~/.herdr-snapshots/<session>-<timestamp>")
    ps.add_argument("--playbooks-dir", default=DEFAULT_PLAYBOOKS_DIR, help="Kommander playbooks root (default: ~/.claude-playbooks)")
    ps.set_defaults(func=cmd_save)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
