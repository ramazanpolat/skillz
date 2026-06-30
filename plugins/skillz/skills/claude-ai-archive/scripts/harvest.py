# claude-ai-archive — harvest script (API-based).
# Recovers conversation→project membership from claude.ai's internal API:
# one logged-in tab, a handful of same-origin fetches. No per-project page
# navigation.
#
# Invoke as:  browser-harness < path/to/harvest.py
#
# Helpers (new_tab, wait_for_load, js, ensure_real_tab) are pre-imported by
# browser-harness.
import datetime as dt
import json
import os
import re
import time
from pathlib import Path

ARCHIVE = Path(os.environ.get("CLAUDE_AI_ARCHIVE", "~/CLAUDE.ai")).expanduser()
projects_dir = ARCHIVE / "projects"

# Read project uuids from each project's CLAUDE.md frontmatter.
archive_projects = {}
for d in sorted(projects_dir.iterdir()):
    cmd = d / "CLAUDE.md"
    if not d.is_dir() or not cmd.exists():
        continue
    fm = cmd.read_text().split("---", 2)[1]
    m_uuid = re.search(r"^uuid:\s*(\S+)", fm, re.M)
    m_name = re.search(r"^name:\s*(.*)$", fm, re.M)
    if m_uuid:
        archive_projects[m_uuid.group(1)] = (m_name.group(1).strip() if m_name else d.name)

print(f"projects in archive: {len(archive_projects)}")


def api(path):
    """Same-origin fetch from the claude.ai tab; poll for the JSON result."""
    js("window.__r=undefined; fetch(" + json.dumps(path)
       + ").then(r=>r.ok?r.json():{'__error':'HTTP '+r.status}).then(d=>{window.__r=d})"
       + ".catch(e=>{window.__r={'__error':String(e)}})")
    for _ in range(40):
        time.sleep(0.5)
        r = js("return window.__r === undefined ? null : window.__r")
        if r is not None:
            if isinstance(r, dict) and "__error" in r:
                raise RuntimeError(f"{path}: {r['__error']}")
            return r
    raise RuntimeError(f"{path}: timeout")


# One tab on claude.ai for same-origin API access; smoke-test login state.
ensure_real_tab()
if not js("return /claude\\.ai/.test(location.host)"):
    new_tab("https://claude.ai/recents")
    wait_for_load()
    time.sleep(1.5)
if js("return /login/.test(location.pathname)"):
    raise SystemExit("not logged into claude.ai (redirected to /login). Log in via Chrome and retry.")

orgs = api("/api/organizations")
if not isinstance(orgs, list) or not orgs:
    raise SystemExit(f"unexpected /api/organizations response: {str(orgs)[:300]}")

# Pick the org whose projects overlap the archive's project uuids.
org_uuid, api_projects = None, []
if len(orgs) == 1:
    org_uuid = orgs[0]["uuid"]
    api_projects = api(f"/api/organizations/{org_uuid}/projects")
else:
    best = -1
    for o in orgs:
        try:
            projs = api(f"/api/organizations/{o['uuid']}/projects")
        except RuntimeError:
            continue
        overlap = sum(1 for p in projs if p["uuid"] in archive_projects)
        if overlap > best:
            best, org_uuid, api_projects = overlap, o["uuid"], projs
print(f"org: {org_uuid}, projects on claude.ai: {len(api_projects)}")

# Fetch every conversation; each carries its project_uuid.
convs, offset = [], 0
while True:
    page = api(f"/api/organizations/{org_uuid}/chat_conversations?limit=100&offset={offset}")
    if not isinstance(page, list):
        raise SystemExit(f"unexpected conversations response at offset {offset}: {str(page)[:300]}")
    convs.extend(page)
    if len(page) < 100:
        break
    offset += 100
print(f"conversations on claude.ai: {len(convs)}")

# Mapping covers archive-known projects only (refile contract). Projects that
# exist on claude.ai but not in the archive go to new_projects_discovered;
# archive projects gone from claude.ai go to errors.
api_by_uuid = {p["uuid"]: p for p in api_projects}
mapping = {u: {"name": api_by_uuid[u]["name"], "chats": []}
           for u in archive_projects if u in api_by_uuid}
errors = [{"project": name, "uuid": u, "reason": "not in claude.ai projects API (deleted?)"}
          for u, name in archive_projects.items() if u not in api_by_uuid]
discovered = [{"uuid": p["uuid"], "name": p["name"]}
              for p in api_projects if p["uuid"] not in archive_projects]

unfiled = 0
for c in convs:
    pu = c.get("project_uuid")
    if pu and pu in mapping:
        mapping[pu]["chats"].append({"uuid": c["uuid"], "title": (c.get("name") or "").strip()})
    else:
        unfiled += 1

out = ARCHIVE / "_phase2_mapping.json"
out.write_text(json.dumps({
    "mapping": mapping,
    "errors": errors,
    "new_projects_discovered": discovered,
}, ensure_ascii=False, indent=2))

ss_path = ARCHIVE / "_sync-state.json"
state = json.loads(ss_path.read_text()) if ss_path.exists() else {}
state["last_harvest_ts"] = dt.datetime.now().isoformat()
ss_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))

total_chats = sum(len(v["chats"]) for v in mapping.values())
print()
print(f"projects mapped: {len(mapping)}/{len(archive_projects)}")
print(f"chat references: {total_chats} in projects, {unfiled} unfiled")
print(f"errors: {len(errors)}, new projects discovered: {len(discovered)}")
for d_ in discovered:
    print(f"  new: {d_['name']} ({d_['uuid']})")
print(f"saved -> {out}")
