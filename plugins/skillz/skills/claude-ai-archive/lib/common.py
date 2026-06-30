"""Shared helpers: paths, sync-state, export loading."""
from __future__ import annotations
import json
import os
import re
import shutil
import zipfile
from pathlib import Path

# Default archive root; override via env or --archive-root.
ARCHIVE_ROOT = Path(os.environ.get("CLAUDE_AI_ARCHIVE", "~/CLAUDE.ai")).expanduser()


def export_path_to_dir(export_path: Path, archive_root: Path) -> Path:
    """Given a .zip or directory, return an extracted directory under raw-export/."""
    raw_root = archive_root / "raw-export"
    raw_root.mkdir(exist_ok=True)
    if export_path.is_dir():
        # Already extracted — copy/link into raw-export keyed by export date
        date = _detect_export_date(export_path)
        dest = raw_root / f"data-{date}"
        # Always materialize the *selected* export: a second export downloaded
        # the same day maps to the same dir, so replace stale contents rather
        # than silently reusing the earlier export's JSON.
        _reset_dir(dest)
        shutil.copytree(export_path, dest)
        _update_latest(raw_root, dest)
        return dest
    if export_path.suffix == ".zip":
        date = _date_from_zip_name(export_path) or _peek_zip_date(export_path)
        dest = raw_root / f"data-{date}"
        _reset_dir(dest)
        dest.mkdir()
        with zipfile.ZipFile(export_path) as zf:
            zf.extractall(dest)
        _update_latest(raw_root, dest)
        return dest
    raise ValueError(f"Not a .zip or directory: {export_path}")


def _reset_dir(dest: Path) -> None:
    """Remove dest if it exists so the selected export's contents win."""
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.is_dir():
        shutil.rmtree(dest)


def _date_from_zip_name(p: Path) -> str | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
    return m.group(1) if m else None


def _peek_zip_date(p: Path) -> str:
    """Fallback: pull a date from the zip's mtime."""
    import datetime as dt
    return dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")


def _detect_export_date(d: Path) -> str:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", d.name)
    if m:
        return m.group(1)
    import datetime as dt
    return dt.datetime.fromtimestamp(d.stat().st_mtime).strftime("%Y-%m-%d")


def _update_latest(raw_root: Path, target: Path) -> None:
    latest = raw_root / "latest"
    if latest.is_symlink() or latest.exists():
        try:
            latest.unlink()
        except IsADirectoryError:
            shutil.rmtree(latest)
    latest.symlink_to(target.name)


def load_export(export_dir: Path) -> dict:
    """Load all the JSON files of an extracted export."""
    out = {
        "users": json.loads((export_dir / "users.json").read_text()),
        "memories": json.loads((export_dir / "memories.json").read_text())[0],
        "conversations": json.loads((export_dir / "conversations.json").read_text()),
        "projects": [],
        "design_chats": [],
    }
    for f in sorted((export_dir / "projects").glob("*.json")):
        out["projects"].append(json.loads(f.read_text()))
    if (export_dir / "design_chats").exists():
        for f in sorted((export_dir / "design_chats").glob("*.json")):
            out["design_chats"].append(json.loads(f.read_text()))
    return out


def read_sync_state(archive_root: Path) -> dict:
    p = archive_root / "_sync-state.json"
    return json.loads(p.read_text()) if p.exists() else {}


def write_sync_state(archive_root: Path, state: dict) -> None:
    (archive_root / "_sync-state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2)
    )


def project_folder_by_uuid(archive_root: Path) -> dict[str, Path]:
    """Walk projects/ and return a {uuid: folder_path} index by reading frontmatter."""
    out = {}
    pdir = archive_root / "projects"
    if not pdir.exists():
        return out
    for d in pdir.iterdir():
        if not d.is_dir():
            continue
        claude_md = d / "CLAUDE.md"
        if not claude_md.exists():
            continue
        try:
            fm = claude_md.read_text().split("---", 2)[1]
            m = re.search(r"^uuid:\s*(\S+)", fm, re.M)
            if m:
                out[m.group(1)] = d
        except Exception:
            pass
    return out


def chat_files_by_uuid(archive_root: Path) -> dict[str, dict[str, Path]]:
    """Walk every .json chat in the archive; return {uuid: {'.md': path, '.json': path}}."""
    out: dict[str, dict[str, Path]] = {}
    for root in (archive_root / "chats-unfiled", archive_root / "projects"):
        if not root.exists():
            continue
        for f in root.rglob("*.json"):
            if f.parent.name == "docs":
                continue
            try:
                d = json.loads(f.read_text())
                cu = d.get("uuid")
                if not cu:
                    continue
                out.setdefault(cu, {})[".json"] = f
                md = f.with_suffix(".md")
                if md.exists():
                    out[cu][".md"] = md
            except Exception:
                pass
    return out
