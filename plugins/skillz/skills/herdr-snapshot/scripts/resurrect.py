#!/usr/bin/env python3
"""Recreate a herdr layout from a snapshot.py capture and resume its playbook sessions.

Two phases, runnable separately or together:

    resurrect.py layout   --snapshot SNAP.json --target-session recovery
    resurrect.py relaunch --snapshot SNAP.instantiated.json --target-session recovery
    resurrect.py all      --snapshot SNAP.json --target-session recovery

`layout` creates every workspace/tab from the snapshot in the target herdr session
(same labels, same cwd) and writes `<snapshot>.instantiated.json` — the same rows
plus the new pane ids to launch into. `relaunch` reads that file and, in small
batches, fires `<launcher> --resume <session>` into every `resume`-decision pane,
checking real memory health between batches (`memory_pressure` free% + swap used —
not raw free-page count, which is misleading on macOS) and stopping rather than
piling on if things look unhealthy. It also catches the two first-run Claude Code
dialogs that default to declining (workspace trust, external-imports trust) and
answers them, since otherwise the pane sits stuck.

Never touches panes whose session is already running elsewhere on the host (checked
via `ps`), and never fires a `duplicate`, `uncertain`, or (unless --include-fresh)
`fresh` row automatically — those need a human call; `relaunch` prints them instead.

This is deliberately conservative about pace: default batch size is 6, with a real
health check after every batch. Override with --batch-size, or use --dry-run to see
the exact plan without touching herdr at all.
"""

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import herdr, resolve_session_socket, memory_health, running_resume_sessions, pid_is_claude  # noqa: E402

TRUST_DIALOG_MARKERS = (
    "trust this folder",
    "external imports",
    "yes, i trust",
    "yes, allow external imports",
)


def load_snapshot(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data


def save_snapshot(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def instantiated_path(snapshot_path):
    base, ext = os.path.splitext(snapshot_path)
    return f"{base}.instantiated{ext}"


# ---------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------

def cmd_layout(args):
    data = load_snapshot(args.snapshot)
    rows = data["tabs"]

    by_ws = {}
    order = []
    for r in rows:
        key = (r["ws_num"], r["ws"])
        if key not in by_ws:
            by_ws[key] = []
            order.append(key)
        by_ws[key].append(r)

    if args.dry_run:
        for key in order:
            wnum, wlabel = key
            tabs = sorted(by_ws[key], key=lambda r: r["tab_num"])
            print(f"workspace {wnum} '{wlabel}': {len(tabs)} tabs")
            for t in tabs:
                print(f"  tab '{t['label']}' cwd={t['cwd']}")
        print(f"\n{len(rows)} tabs across {len(order)} workspaces — dry run, nothing created")
        return 0

    socket_path = resolve_session_socket(args.target_session)

    for key in order:
        wnum, wlabel = key
        tabs = sorted(by_ws[key], key=lambda r: r["tab_num"])
        first = tabs[0]
        print(f"workspace {wnum} '{wlabel}': {len(tabs)} tabs, first='{first['label']}' cwd={first['cwd']}")
        res = json.loads(herdr(["workspace", "create", "--cwd", first["cwd"] or os.path.expanduser("~"),
                                 "--label", wlabel, "--no-focus"], socket_path))["result"]
        new_ws = res["workspace"]["workspace_id"]
        new_tab = res["tab"]["tab_id"]
        new_pane = res["root_pane"]["pane_id"]
        herdr(["tab", "rename", new_tab, first["label"]], socket_path)
        first["new_ws"], first["new_tab"], first["new_pane"] = new_ws, new_tab, new_pane

        for t in tabs[1:]:
            res2 = json.loads(herdr(["tab", "create", "--workspace", new_ws, "--cwd", t["cwd"] or os.path.expanduser("~"),
                                      "--label", t["label"], "--no-focus"], socket_path))["result"]
            t["new_ws"] = new_ws
            t["new_tab"] = res2["tab"]["tab_id"]
            t["new_pane"] = res2["root_pane"]["pane_id"]

    out_path = args.out or instantiated_path(args.snapshot)
    save_snapshot(data, out_path)
    print(f"\nlayout created: {len(rows)} tabs across {len(order)} workspaces")
    print(out_path)
    return 0


# ---------------------------------------------------------------------------
# relaunch
# ---------------------------------------------------------------------------

def answer_trust_dialog(pane_id, socket_path, text):
    low = text.lower()
    if not any(m in low for m in TRUST_DIALOG_MARKERS):
        return False
    herdr(["pane", "send-keys", pane_id, "Down"], socket_path)
    herdr(["pane", "send-keys", pane_id, "Enter"], socket_path)
    return True


def sweep_blocked_panes(socket_path, pane_ids):
    """Check every pane's agent_status; auto-answer recognized trust dialogs. Returns still-blocked list."""
    snap = json.loads(herdr(["api", "snapshot"], socket_path))["result"]["snapshot"]
    status_by_pane = {a["pane_id"]: a.get("agent_status") for a in snap["agents"]}
    still_blocked = []
    for pid in pane_ids:
        if status_by_pane.get(pid) != "blocked":
            continue
        text = herdr(["pane", "read", pid, "--source", "visible", "--lines", "30"], socket_path)
        if answer_trust_dialog(pid, socket_path, text):
            print(f"  {pid}: answered a first-run trust dialog (selected the 'Yes' option)")
            time.sleep(2)
            text2 = herdr(["pane", "read", pid, "--source", "visible", "--lines", "30"], socket_path)
            if answer_trust_dialog(pid, socket_path, text2):
                # a second stacked dialog (e.g. workspace trust, then external-imports trust)
                print(f"  {pid}: answered a second stacked dialog")
        else:
            still_blocked.append(pid)
    return still_blocked


def cmd_relaunch(args):
    data = load_snapshot(args.snapshot)
    rows = data["tabs"]
    socket_path = resolve_session_socket(args.target_session)

    already_running = running_resume_sessions()
    launch, fresh, skip_notes = [], [], []
    for r in rows:
        if not r.get("new_pane"):
            continue
        if r["decision"] == "resume":
            if r["session"] in already_running or pid_is_claude(r.get("pid")):
                skip_notes.append(f"{r['ws']}/{r['label']}: session {r['session'][:8]}… already running elsewhere — skipped")
                continue
            launch.append(r)
        elif r["decision"] == "fresh" and args.include_fresh:
            fresh.append(r)

    print(f"plan: {len(launch)} resume, {len(fresh)} fresh, {len(skip_notes)} already-alive skipped")
    for note in skip_notes:
        print(f"  - {note}")

    if args.dry_run:
        for r in launch:
            print(f"  [resume] {r['new_pane']} <- {r['launcher']} --resume {r['session']}   # {r['ws']}/{r['label']}")
        for r in fresh:
            print(f"  [fresh]  {r['new_pane']} <- {r['launcher']} then pick '{r['task']}'   # {r['ws']}/{r['label']}")
        return 0

    batch_size = args.batch_size
    launched_panes = []
    for i in range(0, len(launch), batch_size):
        batch = launch[i:i + batch_size]
        print(f"\nbatch {i // batch_size + 1}: {len(batch)} panes")
        for r in batch:
            cmd = f"{r['launcher']} --resume {r['session']}"
            herdr(["pane", "run", r["new_pane"], cmd], socket_path)
            launched_panes.append(r["new_pane"])
            print(f"  {r['new_pane']} <- {cmd}   # {r['ws']}/{r['label']}")

        time.sleep(args.settle_seconds)
        free_pct, swap_used = memory_health()
        print(f"  memory: {free_pct}% free, {swap_used}MB swap used")
        if swap_used and swap_used > 0:
            print(f"  STOPPING: swap in use ({swap_used}MB) — host is under real memory pressure. "
                  f"{len(launch) - i - len(batch)} panes not yet launched.")
            break
        if free_pct is not None and free_pct < args.min_free_pct:
            print(f"  STOPPING: free memory {free_pct}% is below --min-free-pct {args.min_free_pct}%. "
                  f"{len(launch) - i - len(batch)} panes not yet launched.")
            break

    if fresh:
        print(f"\nfresh-start tabs ({len(fresh)}):")
        for r in fresh:
            herdr(["pane", "run", r["new_pane"], r["launcher"]], socket_path)
            try:
                herdr(["wait", "output", r["new_pane"], "--match", "Type the task name", "--timeout", "20000"], socket_path)
                herdr(["pane", "run", r["new_pane"], r["task"]], socket_path)
                print(f"  {r['new_pane']}: launched {r['launcher']}, picked task '{r['task']}'   # {r['ws']}/{r['label']}")
                launched_panes.append(r["new_pane"])
            except RuntimeError:
                print(f"  {r['new_pane']}: launched {r['launcher']} but the task picker never appeared — check manually")

    print("\nsweeping for blocked panes (first-run trust dialogs)...")
    time.sleep(3)
    still_blocked = sweep_blocked_panes(socket_path, launched_panes)
    if still_blocked:
        print(f"  {len(still_blocked)} pane(s) still blocked on something unrecognized — check manually: {', '.join(still_blocked)}")
    else:
        print("  none")

    uncertain = [r for r in rows if r["decision"] == "uncertain"]
    duplicate = [r for r in rows if r["decision"] == "duplicate"]
    not_included_fresh = [r for r in rows if r["decision"] == "fresh" and not args.include_fresh]
    if uncertain:
        print(f"\n{len(uncertain)} tab(s) left for a human call (not auto-launched):")
        for r in uncertain:
            print(f"  - {r['ws']}/{r['label']}: {r['note']}")
    if not_included_fresh:
        print(f"\n{len(not_included_fresh)} fresh-start tab(s) skipped (pass --include-fresh to launch them):")
        for r in not_included_fresh:
            print(f"  - {r['ws']}/{r['label']}: {r['playbook']}/{r['task']}")
    if duplicate:
        print(f"\n{len(duplicate)} duplicate tab(s) correctly left empty: " +
              ", ".join(f"{r['ws']}/{r['label']}" for r in duplicate))

    return 0


def cmd_all(args):
    if args.dry_run:
        print("(--dry-run: showing the layout plan only — relaunch needs real pane ids from an actual layout run)\n")
        return cmd_layout(args)
    rc = cmd_layout(args)
    if rc != 0:
        return rc
    args.snapshot = args.out or instantiated_path(args.snapshot)
    return cmd_relaunch(args)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--snapshot", required=True, help="snapshot JSON from snapshot.py save (or its .instantiated.json)")
    common.add_argument("--target-session", required=True, help="herdr session name to build/relaunch into (see `herdr session list`)")

    pl = sub.add_parser("layout", parents=[common], help="recreate workspaces/tabs only")
    pl.add_argument("--out", help="instantiated snapshot output path (default: <snapshot>.instantiated.json)")
    pl.add_argument("--dry-run", action="store_true", help="print the workspace/tab plan, touch nothing")
    pl.set_defaults(func=cmd_layout)

    pr = sub.add_parser("relaunch", parents=[common], help="batch-resume sessions into an already-built layout")
    pr.add_argument("--batch-size", type=int, default=6)
    pr.add_argument("--settle-seconds", type=int, default=10, help="pause after each batch before checking memory")
    pr.add_argument("--min-free-pct", type=int, default=25, help="stop launching if memory_pressure free%% drops below this")
    pr.add_argument("--include-fresh", action="store_true", help="also launch 'fresh' tabs (no session — picks the task from the menu)")
    pr.add_argument("--dry-run", action="store_true", help="print the plan, touch nothing")
    pr.set_defaults(func=cmd_relaunch)

    pa = sub.add_parser("all", parents=[common], help="layout then relaunch")
    pa.add_argument("--out", help=argparse.SUPPRESS)
    pa.add_argument("--batch-size", type=int, default=6)
    pa.add_argument("--settle-seconds", type=int, default=10)
    pa.add_argument("--min-free-pct", type=int, default=25)
    pa.add_argument("--include-fresh", action="store_true")
    pa.add_argument("--dry-run", action="store_true")
    pa.set_defaults(func=cmd_all)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
