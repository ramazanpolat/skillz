# skillz

Ramazan's personal collection of [Claude Code](https://claude.com/claude-code)
**skills**, packaged as a plugin marketplace so that many skills can live in a
single repository and be installed with one command.

---

## What is a skill?

A *skill* is a folder containing a `SKILL.md` file with YAML frontmatter
(`name` + `description`) and, optionally, helper scripts. Claude Code reads the
`description` and **invokes the skill automatically** when your request matches —
no manual command needed. Skills let you teach Claude reusable, project- or
machine-specific procedures (here: how to move files to a particular host).

This repo distributes its skills through a **plugin marketplace**, the native
Claude Code mechanism for sharing and installing collections of skills, commands,
agents, and hooks.

---

## Install

```text
/plugin marketplace add ramazanpolat/skillz
/plugin install skillz@skillz
```

- The first line registers this repo as a marketplace.
- The second installs the `skillz` plugin and every skill it bundles.
- Update later with `/plugin` (manage installed plugins) and re-run install to
  pick up new skills.

Verify with `/plugin` — the `skillz` plugin and its skills should be listed.

---

## Skills in this repo

| Skill | What it does |
|-------|--------------|
| [`file-transfer`](plugins/skillz/skills/file-transfer/SKILL.md) | Push/pull files to/from the `macminim` Mac mini (or any passwordless-SSH host) using `rsync` over SSH. |
| [`claude-ai-archive`](plugins/skillz/skills/claude-ai-archive/SKILL.md) | Import/sync a claude.ai data export into a local on-disk mirror (`~/CLAUDE.ai/`); recovers conversation→project mapping via browser-harness. |
| [`sprite`](plugins/skillz/skills/sprite/SKILL.md) | Sprite ([sprites.dev](https://sprites.dev/)) VM environment agent: services, checkpoints/restores, dev servers, and network policy via the in-VM `sprite-env` CLI. |
| [`sprite-api-gateway`](plugins/skillz/skills/sprite-api-gateway/SKILL.md) | Access external APIs (GitHub, Slack, Linear, …) from a Sprite through the authenticated `api.sprites.dev` gateway — no raw API keys. |
| [`test-on-sprite`](plugins/skillz/skills/test-on-sprite/SKILL.md) | Test a repo in a disposable Sprite VM: provision a sprite per target, authenticate Claude + GitHub, checkpoint a reset point, then clone at a branch and run install/tests — driven through a live herdr console pane. |
| [`herdr`](plugins/skillz/skills/herdr/SKILL.md) | Control herdr (terminal-native agent multiplexer) from inside it. **Modified fork** of herdr's own skill (AGPL-3.0) with corrected pane self-identification. See [License](#license). |

### file-transfer

Moves files between your machine and a remote host that already accepts
**passwordless SSH** (key-based auth). Wraps `rsync -avz` over SSH, so transfers
are recursive, resumable, and skip unchanged files. Default host is `macminim`.

```bash
transfer.sh push <local-path> [remote-dest]   # local  -> remote (default dest: ~/)
transfer.sh pull <remote-path> [local-dest]   # remote -> local  (default dest: .)
transfer.sh ls   [remote-path]                # list a remote directory
```

Options: `-H/--host <alias>` (or `$SKILLZ_HOST`) to target another host,
`-n/--dry-run` to preview, `-h/--help` for full help.

Examples:

```bash
transfer.sh push ./report.pdf                # -> macminim:~/report.pdf
transfer.sh push ./build/ ~/deploys/app/     # trailing slash = copy CONTENTS
transfer.sh pull ~/logs/app.log ./logs/      # macminim -> ./logs/
transfer.sh -H macmini2 push ./data.csv      # different host
```

In practice you don't call the script by hand — just ask Claude Code something
like *"send report.pdf to macminim"* or *"pull ~/logs/app.log from macminim"* and
the skill fires.

**Prerequisites:** `ssh <host>` connects without a password (test:
`ssh -o BatchMode=yes macminim true`), and `rsync` is installed on both ends
(standard on macOS).

### claude-ai-archive

Keeps a local, greppable mirror of your claude.ai content at `~/CLAUDE.ai/` —
every chat as a `.md` + `.json` pair, every project as a folder you can `cd`
into. Takes a claude.ai **data export** (Settings → Account → Export data) and
builds or updates the archive; a browser-harness pass recovers the
conversation→project mapping the export omits.

```bash
# from the skill directory
python scripts/archive.py import --export <export.zip>   # first-time build
python scripts/archive.py sync   --export <export.zip>   # apply a newer export
browser-harness < scripts/harvest.py                     # recover project mapping
python scripts/archive.py refile                         # file chats into projects
python scripts/archive.py status                         # counts + sync state
```

In practice you just ask Claude Code *"import my claude.ai export"* or *"sync the
CLAUDE.ai archive"* and the skill fires. Archive root defaults to `~/CLAUDE.ai`
(override with `--archive-root` or `$CLAUDE_AI_ARCHIVE`).

**Prerequisites:** [`browser-harness`](https://github.com/) on `$PATH` and a
Chrome session logged into claude.ai (for the mapping pass), plus Python 3.

### herdr

Lets an agent control [herdr](https://github.com/ogulcancelik/herdr) — a
terminal-native agent multiplexer — from inside a herdr-managed pane: list/split
panes, run commands in siblings, wait for output or agent status, manage
workspaces and tabs. Active when `HERDR_ENV=1`.

> **This is a modified fork of herdr's own agent skill**, not original work.
> The upstream skill told agents *"the focused pane is yours,"* which is wrong
> when several agents run across workspaces — `focused: true` and the `--current`
> flag follow the **user's UI focus**, not the calling shell, so splits land in
> the wrong workspace. This fork teaches self-identification via `$HERDR_PANE_ID`
> and `herdr pane current` and passes explicit pane ids. herdr is licensed
> **AGPL-3.0-or-later**; this modified copy is redistributed under the same
> license with attribution — which is why this whole repo is AGPL (see
> [License](#license)). Upstream: https://github.com/ogulcancelik/herdr.

---

## Repository layout

```text
skillz/
├── README.md                          # this file
├── LICENSE                            # AGPL-3.0-or-later (full text)
├── NOTICE                             # third-party attribution (herdr skill)
├── .claude-plugin/
│   └── marketplace.json               # marketplace manifest → lists the skillz plugin
└── plugins/
    └── skillz/
        ├── .claude-plugin/
        │   └── plugin.json            # plugin manifest (name, version, author)
        ├── README.md
        └── skills/                    # one folder per skill
            ├── file-transfer/
            │   ├── SKILL.md           # frontmatter (name/description) + instructions
            │   └── scripts/
            │       └── transfer.sh    # helper script the skill calls
            ├── claude-ai-archive/
            │   ├── SKILL.md
            │   ├── config.json        # archive root + export search defaults
            │   ├── lib/               # shared helpers (export loading, render, slug)
            │   └── scripts/           # archive.py (import/sync/refile/status), harvest.py
            └── herdr/                 # MODIFIED fork of herdr's skill (AGPL-3.0)
                └── SKILL.md
```

- **`marketplace.json`** advertises one plugin, `skillz`, sourced from
  `./plugins/skillz`.
- **`plugin.json`** is the plugin's manifest. Skills are auto-discovered from the
  plugin's `skills/` directory — they are **not** enumerated in the manifest.

---

## Adding a new skill

1. Create `plugins/skillz/skills/<new-skill>/SKILL.md` with frontmatter:

   ```markdown
   ---
   name: <new-skill>
   description: <when Claude should use this skill — be specific; this is the trigger>
   ---

   # <new-skill>

   Instructions for Claude on how to perform the task.
   ```

2. Put any helper scripts under that skill's own `scripts/` folder and `chmod +x`
   them.
3. Commit and push. Users pick it up on the next `/plugin` update — no edits to
   `marketplace.json` or `plugin.json` required.

---

## License

**AGPL-3.0-or-later** (see [`LICENSE`](LICENSE)).

This repository bundles a modified version of herdr's agent skill
(`plugins/skillz/skills/herdr/`), which is licensed AGPL-3.0-or-later. Because
the repo redistributes that copyleft work, the repository as a whole is
distributed under AGPL-3.0-or-later. Third-party attribution and the list of
modifications are in [`NOTICE`](NOTICE).

herdr is dual-licensed (AGPL or commercial); the original project is at
https://github.com/ogulcancelik/herdr. No warranty.
