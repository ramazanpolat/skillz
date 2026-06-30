#!/usr/bin/env python3
"""claude-ai-archive — import, sync, refile, status.

Usage:
    archive.py import  --export <path> [--archive-root <dir>]
    archive.py sync    --export <path> [--archive-root <dir>]
    archive.py refile  [--archive-root <dir>]
    archive.py status  [--archive-root <dir>]
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
from slug import slugify  # type: ignore
from render import render_conversation, render_design_chat, render_project  # type: ignore
from common import (  # type: ignore
    ARCHIVE_ROOT,
    chat_files_by_uuid,
    export_path_to_dir,
    load_export,
    project_folder_by_uuid,
    read_sync_state,
    write_sync_state,
)


# --- write helpers ---

def write_conversation(conv: dict, target_dir: Path, archived: bool = False) -> Path:
    """Write a .md + .json pair for one conversation, return base path (no ext)."""
    uuid = conv["uuid"]
    name = conv.get("name") or "untitled"
    created = (conv.get("created_at") or "")[:10] or "undated"
    short = uuid.split("-")[0]
    base = f"{created}_{slugify(name, 60)}_{short}"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / f"{base}.md").write_text(render_conversation(conv, archived=archived))
    (target_dir / f"{base}.json").write_text(json.dumps(conv, ensure_ascii=False, indent=2))
    return target_dir / base


def write_project(p: dict, memory: str, archive_root: Path,
                  existing_folders: dict[str, Path]) -> Path:
    """Create or update a project folder. Returns the folder path."""
    uuid = p["uuid"]
    name = p["name"]
    docs = p.get("docs", []) or []

    pdir = existing_folders.get(uuid)
    if pdir is None:
        # Probe for a folder not already taken by another project — on disk OR
        # assigned earlier in this run. Folders are keyed by UUID, so a new
        # project whose name slugifies onto an existing folder must get its own
        # path; reusing it would overwrite the other project.
        taken = {fp.name for fp in existing_folders.values()}
        base = slugify(name)
        slug, n = base, 1
        while slug in taken or (archive_root / "projects" / slug).exists():
            n += 1
            slug = f"{base}-{n}"
        pdir = archive_root / "projects" / slug
        pdir.mkdir(parents=True)
        existing_folders[uuid] = pdir
    (pdir / "chats").mkdir(exist_ok=True)
    (pdir / "CLAUDE.md").write_text(render_project(p, memory))

    # Reconcile docs/ to the new export. When the export has no docs (all were
    # deleted), drop the whole dir so stale docs don't linger in the mirror.
    docs_dir = pdir / "docs"
    if docs:
        docs_dir.mkdir(exist_ok=True)
        # Track which doc filenames are in the new export — anything else is stale
        wanted = set()
        seen: Counter = Counter()
        for d in docs:
            fn = d.get("filename", "untitled.txt")
            stem, ext = Path(fn).stem, Path(fn).suffix or ".md"
            seen[fn] += 1
            if seen[fn] > 1:
                fn = f"{stem}_{seen[fn]}{ext}"
            (docs_dir / fn).write_text(d.get("content", "") or "")
            wanted.add(fn)
        for existing in docs_dir.iterdir():
            if existing.name not in wanted:
                existing.unlink()
    elif docs_dir.exists():
        shutil.rmtree(docs_dir)
    return pdir


def write_design_chat(d: dict, archive_root: Path) -> None:
    out = archive_root / "design-chats"
    out.mkdir(exist_ok=True)
    uuid = d.get("uuid", "")
    short = uuid.split("-")[0]
    title = d.get("title") or "design-chat"
    created = (d.get("created_at") or "")[:10]
    base = f"{created}_{slugify(title)}_{short}"
    (out / f"{base}.md").write_text(render_design_chat(d))
    (out / f"{base}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2))


def mark_archived_in_frontmatter(path: Path) -> None:
    """Add `archived: true` to the YAML frontmatter of a .md file (idempotent)."""
    if not path.exists():
        return
    text = path.read_text()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return
    fm = parts[1]
    if re.search(r"^archived:\s*true", fm, re.M):
        return
    fm = fm.rstrip("\n") + "\narchived: true\n"
    path.write_text(parts[0] + "---" + fm + "---" + parts[2])


# --- root files ---

def write_root_files(archive_root: Path, export_date: str, counts: dict) -> None:
    archive_root.mkdir(exist_ok=True)
    (archive_root / "global-memory.md").write_text(counts["global_memory_text"])

    root_claude = archive_root / "CLAUDE.md"
    if not root_claude.exists():
        root_claude.write_text(_default_root_claude())

    readme = (
        "# CLAUDE.ai — faithful mirror of your claude.ai content\n\n"
        f"Built from a claude.ai export (latest: {export_date}). Updated by the `claude-ai-archive` skill.\n\n"
        "Each chat exists as a `.md` + `.json` pair with the same base name. The .md is for reading and grep; "
        "the .json is the raw export record. The root `CLAUDE.md` and per-project `CLAUDE.md` are auto-loaded "
        "by Claude Code when you `cd` into the folder.\n\n"
        f"Provenance: {counts['n_projects']} projects, {counts['n_convs']} conversations, "
        f"{counts['n_design']} design chats. Last refresh: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}.\n"
    )
    (archive_root / "README.md").write_text(readme)


def _default_root_claude() -> str:
    return (
        "# CLAUDE.ai archive\n\n"
        "Local mirror of the user's claude.ai content. Projects are folders under `projects/<slug>/`; "
        "free chats live in `chats-unfiled/YYYY/`; every chat is a `.md` + `.json` pair. The `raw-export/latest` "
        "symlink points at the most recent export. Refresh with the `/claude-ai-archive` skill.\n\n"
        "Search past chats with ripgrep over `chats-unfiled/` and `projects/*/chats/`. To resume work on a "
        "claude.ai project, `cd projects/<slug>/` — its CLAUDE.md is loaded automatically.\n\n"
        "Do not edit through `raw-export/`. Treat `chats/` and `chats-unfiled/` as read-only history.\n"
    )


def write_index(archive_root: Path) -> None:
    pdir = archive_root / "projects"
    rows = []
    for d in sorted(pdir.iterdir() if pdir.exists() else []):
        if not d.is_dir():
            continue
        claude_md = d / "CLAUDE.md"
        if not claude_md.exists():
            continue
        fm = claude_md.read_text().split("---", 2)[1]

        def f(k: str, default: str = "") -> str:
            m = re.search(rf"^{k}:\s*(.*)$", fm, re.M)
            return m.group(1).strip() if m else default

        chats_dir = d / "chats"
        n_chats = sum(1 for x in chats_dir.iterdir() if x.suffix == ".json") if chats_dir.exists() else 0
        docs_dir = d / "docs"
        n_docs = sum(1 for _ in docs_dir.iterdir()) if docs_dir.exists() else 0
        rows.append({
            "name": f("name"), "folder": d.name, "chats": n_chats, "docs": n_docs,
            "has_mem": f("has_project_memory") == "True", "created": f("created_at")[:10],
            "archived": f("archived") == "true",
        })

    unfiled = 0
    unfiled_dir = archive_root / "chats-unfiled"
    if unfiled_dir.exists():
        for yd in unfiled_dir.iterdir():
            if yd.is_dir():
                unfiled += sum(1 for f in yd.iterdir() if f.suffix == ".json")
    design = sum(1 for f in (archive_root / "design-chats").iterdir() if f.suffix == ".json") \
        if (archive_root / "design-chats").exists() else 0

    out = ["# claude.ai content index", "", "## Projects", "",
           "| project | folder | chats | docs | memory | archived | created |",
           "|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: -x["chats"]):
        out.append(
            f"| {r['name']} | `projects/{r['folder']}/` | {r['chats']} | {r['docs']} | "
            f"{'yes' if r['has_mem'] else '—'} | {'yes' if r['archived'] else '—'} | {r['created']} |"
        )
    in_projects = sum(r["chats"] for r in rows)
    out.extend([
        "", "## Totals", "",
        f"- In projects: **{in_projects}**",
        f"- Unfiled: **{unfiled}** (in `chats-unfiled/`)",
        f"- Design chats: **{design}**",
        f"- Grand total: **{in_projects + unfiled + design}**", "",
    ])
    (archive_root / "INDEX.md").write_text("\n".join(out) + "\n")


# --- modes ---

def cmd_import(args: argparse.Namespace, *, sync: bool = False) -> None:
    archive_root = Path(args.archive_root).expanduser()
    archive_root.mkdir(exist_ok=True)
    export = Path(args.export).expanduser().resolve()
    if not export.exists():
        sys.exit(f"export not found: {export}")

    print(f"→ extracting export: {export}")
    export_dir = export_path_to_dir(export, archive_root)
    print(f"→ raw-export/{export_dir.name}")

    data = load_export(export_dir)
    project_mems = data["memories"]["project_memories"]

    # Walk existing state
    folders = project_folder_by_uuid(archive_root)
    chat_files = chat_files_by_uuid(archive_root)
    known_chats = set(chat_files.keys())
    known_projects = set(folders.keys())

    new_export_chat_uuids = {c["uuid"] for c in data["conversations"]}
    new_export_project_uuids = {p["uuid"] for p in data["projects"]}

    # Projects: write/update each
    print(f"→ {len(data['projects'])} projects in export")
    for p in data["projects"]:
        write_project(p, project_mems.get(p["uuid"], ""), archive_root, folders)

    # Mark archived: projects that disappeared from new export
    disappeared_projects = known_projects - new_export_project_uuids
    for puuid in disappeared_projects:
        mark_archived_in_frontmatter(folders[puuid] / "CLAUDE.md")

    # Conversations: write into chats-unfiled/ unless already filed.
    # Updated convs get rewritten in-place wherever they live.
    n_new = n_updated = n_unchanged = 0
    for conv in data["conversations"]:
        cu = conv["uuid"]
        existing = chat_files.get(cu)
        if existing:
            # Check updated_at
            try:
                exist_data = json.loads(existing[".json"].read_text())
                if exist_data.get("updated_at") == conv.get("updated_at"):
                    n_unchanged += 1
                    continue
            except Exception:
                pass
            # Rewrite in place
            base_dir = existing[".json"].parent
            for ext in (".md", ".json"):
                if ext in existing:
                    existing[ext].unlink()
            write_conversation(conv, base_dir)
            n_updated += 1
        else:
            year = (conv.get("created_at") or "")[:4] or "undated"
            write_conversation(conv, archive_root / "chats-unfiled" / year)
            n_new += 1

    # Mark archived: chats that disappeared from new export
    disappeared_chats = known_chats - new_export_chat_uuids
    for cu in disappeared_chats:
        files = chat_files[cu]
        if ".md" in files:
            mark_archived_in_frontmatter(files[".md"])

    # Design chats
    print(f"→ {len(data['design_chats'])} design chats")
    for d in data["design_chats"]:
        write_design_chat(d, archive_root)

    # Root files
    counts = {
        "n_projects": len(data["projects"]),
        "n_convs": len(data["conversations"]),
        "n_design": len(data["design_chats"]),
        "global_memory_text": (
            "# Conversations memory (global, from claude.ai)\n\n"
            "_Cross-conversation memory claude.ai kept about you._\n\n---\n\n"
            f"{data['memories']['conversations_memory'].strip()}\n"
        ),
    }
    write_root_files(archive_root, export_date=export_dir.name.replace("data-", ""), counts=counts)
    write_index(archive_root)

    state = read_sync_state(archive_root)
    state.update({
        "last_export_path": str(export),
        "last_export_date": export_dir.name.replace("data-", ""),
        "last_action_ts": dt.datetime.now().isoformat(),
        "last_action": "sync" if sync else "import",
        "n_projects": len(data["projects"]),
        "n_conversations": len(data["conversations"]),
    })
    write_sync_state(archive_root, state)

    print()
    print(f"  +{n_new} new chats, ~{n_updated} updated, {n_unchanged} unchanged")
    print(f"  disappeared: {len(disappeared_chats)} chats, {len(disappeared_projects)} projects (marked archived: true)")
    print(f"  archive: {archive_root}")
    print(f"  next: run browser-harness harvest, then `archive.py refile`")


def cmd_refile(args: argparse.Namespace) -> None:
    archive_root = Path(args.archive_root).expanduser()
    mapping_file = archive_root / "_phase2_mapping.json"
    if not mapping_file.exists():
        sys.exit(f"missing mapping file: {mapping_file}. Run the harvest step first.")
    mapping = json.loads(mapping_file.read_text()).get("mapping", {})

    folders = project_folder_by_uuid(archive_root)
    chats = chat_files_by_uuid(archive_root)

    # Build chat_uuid -> target project_uuid
    target: dict[str, str] = {}
    for puuid, info in mapping.items():
        for c in info.get("chats", []):
            target[c["uuid"]] = puuid

    moved = misplaced_to_unfiled = 0
    for cu, files in chats.items():
        if ".json" not in files:
            continue
        current_dir = files[".json"].parent
        wanted_puuid = target.get(cu)
        wanted_dir = (folders.get(wanted_puuid) / "chats") if wanted_puuid and wanted_puuid in folders else None
        if wanted_dir is None:
            # Should be in chats-unfiled
            if current_dir.name != "chats" or current_dir.parent.parent.name != "projects":
                continue  # already unfiled or design-chats — leave
            year = files[".json"].name[:4]
            new_dir = archive_root / "chats-unfiled" / year
            new_dir.mkdir(parents=True, exist_ok=True)
            for ext in (".md", ".json"):
                if ext in files:
                    shutil.move(str(files[ext]), str(new_dir / files[ext].name))
            misplaced_to_unfiled += 1
            continue
        if current_dir == wanted_dir:
            continue
        wanted_dir.mkdir(parents=True, exist_ok=True)
        for ext in (".md", ".json"):
            if ext in files:
                shutil.move(str(files[ext]), str(wanted_dir / files[ext].name))
        moved += 1

    # Prune empty year dirs in chats-unfiled
    unfiled = archive_root / "chats-unfiled"
    if unfiled.exists():
        for yd in unfiled.iterdir():
            if yd.is_dir() and not any(yd.iterdir()):
                yd.rmdir()

    write_index(archive_root)

    state = read_sync_state(archive_root)
    state["last_refile_ts"] = dt.datetime.now().isoformat()
    write_sync_state(archive_root, state)

    print(f"refiled: {moved} into projects, {misplaced_to_unfiled} back to chats-unfiled")
    print(f"INDEX.md regenerated.")


def cmd_status(args: argparse.Namespace) -> None:
    archive_root = Path(args.archive_root).expanduser()
    if not archive_root.exists():
        sys.exit(f"no archive at {archive_root}")
    state = read_sync_state(archive_root)
    folders = project_folder_by_uuid(archive_root)
    chats = chat_files_by_uuid(archive_root)

    in_projects = 0
    archived_projects = 0
    archived_chats = 0
    for cu, files in chats.items():
        if ".json" not in files:
            continue
        parent = files[".json"].parent
        if parent.name == "chats" and parent.parent.parent.name == "projects":
            in_projects += 1
        if ".md" in files:
            text = files[".md"].read_text(errors="ignore")[:1000]
            if re.search(r"^archived:\s*true", text, re.M):
                archived_chats += 1
    for puuid, folder in folders.items():
        text = (folder / "CLAUDE.md").read_text(errors="ignore")[:2000]
        if re.search(r"^archived:\s*true", text, re.M):
            archived_projects += 1
    total = len(chats)
    unfiled = total - in_projects

    print(f"archive: {archive_root}")
    print(f"  projects: {len(folders)} (archived: {archived_projects})")
    print(f"  chats:    {total} ({in_projects} in projects, {unfiled} unfiled, {archived_chats} archived)")
    print(f"  last action: {state.get('last_action', '—')} at {state.get('last_action_ts', '—')}")
    print(f"  last export: {state.get('last_export_path', '—')} ({state.get('last_export_date', '—')})")
    print(f"  last refile: {state.get('last_refile_ts', '—')}")
    print(f"  last harvest: {state.get('last_harvest_ts', '—')}")


# --- argparse ---

def main() -> None:
    ap = argparse.ArgumentParser(description="claude-ai-archive")
    sub = ap.add_subparsers(dest="mode", required=True)
    for m in ("import", "sync"):
        sp = sub.add_parser(m)
        sp.add_argument("--export", required=True)
        sp.add_argument("--archive-root", default=str(ARCHIVE_ROOT))
    sp = sub.add_parser("refile")
    sp.add_argument("--archive-root", default=str(ARCHIVE_ROOT))
    sp = sub.add_parser("status")
    sp.add_argument("--archive-root", default=str(ARCHIVE_ROOT))

    args = ap.parse_args()
    if args.mode == "import":
        cmd_import(args, sync=False)
    elif args.mode == "sync":
        cmd_import(args, sync=True)
    elif args.mode == "refile":
        cmd_refile(args)
    elif args.mode == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
