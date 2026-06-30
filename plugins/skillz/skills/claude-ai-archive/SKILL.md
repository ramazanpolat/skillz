---
name: claude-ai-archive
description: Import a claude.ai data export into ~/CLAUDE.ai/, or sync the archive against a newer export. Use when the user mentions importing claude.ai data, syncing claude conversations, refreshing the ~/CLAUDE.ai/ archive, or managing the local mirror of their claude.ai content. Also handles the browser-harness pass that recovers conversation→project mapping (which the export omits).
---

# claude-ai-archive

Manages a local mirror of the user's claude.ai content (default `~/CLAUDE.ai/`). The archive is a replacement for claude.ai project search — every chat is on disk as a `.md` + `.json` pair, every project is a folder you can `cd` into.

Run the bundled scripts **from this skill's directory** (paths below are relative
to it). The archive root defaults to `~/CLAUDE.ai`; override with `--archive-root`
or the `CLAUDE_AI_ARCHIVE` environment variable.

## Modes

The skill has four modes. Determine which from the user's wording. If they invoked `/claude-ai-archive` with no extra context, **auto-detect**: import if `<archive-root>/INDEX.md` does not exist, otherwise sync.

| mode | what it does | needs browser-harness |
|---|---|---|
| `import` | first-time build from an export zip/dir | yes |
| `sync`   | apply a newer export as a delta against the existing archive | yes |
| `remap`  | re-scrape project→chat membership only (no new export) | yes |
| `status` | print counts and sync-state without changes | no |

## Step 1 — locate the export (skip for `remap` and `status`)

If the user did not provide a path:

1. If `<archive-root>/_sync-state.json` exists, read its `last_export_path` as a candidate.
2. Search `~/Downloads/`, `~/DEV/`, and `~/` (in that order) for files matching `claude-ai-data-exported-*.zip`.
3. If exactly one fresh candidate found, confirm with the user and use it.
4. If multiple candidates, list them with dates and ask which.
5. If none found, tell the user how to export from claude.ai (Settings → Account → Export data) and stop.

Accept either a `.zip` or an already-extracted directory.

## Step 2 — run the data import (skip for `remap` and `status`)

```bash
python scripts/archive.py <mode> --export <path> [--archive-root ~/CLAUDE.ai]
```

Where `<mode>` is `import` or `sync`. The script handles:

- unzipping into `<archive-root>/raw-export/data-YYYY-MM-DD/` (keeps prior exports, repoints the `raw-export/latest` symlink)
- creating/updating `projects/<slug>/CLAUDE.md` (project memory + prompt template + description, with YAML frontmatter) and `projects/<slug>/docs/`
- writing each conversation as a paired `.md` + `.json` in `chats-unfiled/YYYY/` (chats already filed into projects stay where they are; the refile step in Step 4 handles new placements)
- regenerating `global-memory.md`, the root `CLAUDE.md`, `README.md`, `INDEX.md`
- updating `_sync-state.json` with timestamps, export path, counts

Sync semantics:

- **new chat uuid** → write into `chats-unfiled/YYYY/`; Step 4 will refile it.
- **chat uuid exists, `updated_at` newer in new export** → overwrite the `.md` + `.json` pair in place; don't move folders.
- **chat uuid exists in archive but missing from new export** → add `archived: true` to the `.md` frontmatter (do not delete).
- **new project** → create `projects/<slug>/CLAUDE.md` + empty `chats/` + `docs/`.
- **project description / memory / prompt_template / docs changed** → overwrite `CLAUDE.md` and `docs/<filename>`.
- **project missing from new export** → add `archived: true` to its `CLAUDE.md` frontmatter (do not delete).

The script is idempotent — re-running with the same export is a no-op.

## Step 3 — browser-harness mapping pass (skip for `status`)

The export does not carry conversation→project linkage. Recover it from logged-in claude.ai. Required before refile.

```bash
browser-harness < scripts/harvest.py
```

(browser-harness takes the script on stdin; it has no `-c` flag.)

The script opens one logged-in claude.ai tab and uses the internal API — `/api/organizations/<org>/projects` plus paginated `/api/organizations/<org>/chat_conversations`, where every conversation record carries its `project_uuid` — to rebuild `<archive-root>/_phase2_mapping.json`. No per-project page navigation. If the account has multiple organizations, it picks the one whose projects overlap the archive's project uuids.

Projects that exist on claude.ai but not in the archive are written under `new_projects_discovered` for the user to inspect; archive projects missing from claude.ai are listed under `errors`.

If browser-harness fails (Chrome not logged in, CDP unreachable, etc.):

- STOP and report the error to the user.
- Tell them new chats are sitting in `chats-unfiled/YYYY/`.
- They can run `/claude-ai-archive remap` once they fix the login.

Expect ~10-20 seconds total regardless of project count (a handful of API fetches).

## Step 4 — refile chats based on the mapping (skip for `status`)

```bash
python scripts/archive.py refile
```

This reads `_phase2_mapping.json`, walks `chats-unfiled/` and the existing `projects/*/chats/` folders to locate every chat by uuid, and:

- moves chats now claimed by a project from `chats-unfiled/` into `projects/<slug>/chats/`
- moves chats that have **left** their old project (e.g., a chat reassigned in claude.ai) into the new project or back to `chats-unfiled/` if it's no longer in any project
- prunes empty year folders under `chats-unfiled/`
- regenerates `INDEX.md` with final counts

Refile is also idempotent.

## Step 5 — report

After Step 4 (or Step 1 for `status`), print a concise summary:

- mode and what happened (`+12 new chats, ~3 updated, +1 new project, 0 archived`)
- counts (projects, chats in projects, chats unfiled, design chats)
- location and what to do next (e.g., `cd ~/CLAUDE.ai/projects/<slug>/` to resume work)
- last sync timestamp from `_sync-state.json`

## Notes

- The archive's root `CLAUDE.md` and per-project `CLAUDE.md` are auto-loaded by Claude Code when you `cd` into the folder. Do not rename them.
- `raw-export/` is a directory containing past exports verbatim; `raw-export/latest` is a symlink to the most recent. Never edit through it.
- `_phase2_mapping.json` is provenance for the refile step. Regenerate via `remap`; don't edit by hand.
- The archive root defaults to `~/CLAUDE.ai`. Point it elsewhere with `--archive-root <dir>` or `export CLAUDE_AI_ARCHIVE=<dir>` (the harvest step reads the same variable).
- Requires [`browser-harness`](https://github.com/) on `$PATH` and a Chrome session already logged into claude.ai for the mapping pass (Steps 3 / `remap`).
- If the user asks to back up the archive, recommend `rsync -a ~/CLAUDE.ai/ <dest>/`.
