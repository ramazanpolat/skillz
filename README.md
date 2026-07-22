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
| [`croc`](plugins/skillz/skills/croc/SKILL.md) | **Default for sending.** Files, folders, or text to **any** computer (no SSH needed) with [`croc`](https://github.com/schollz/croc) — peer-to-peer, end-to-end encrypted via a one-time code phrase; no server, no accounts. |
| [`file-transfer`](plugins/skillz/skills/file-transfer/SKILL.md) | Specialist for **passwordless-SSH hosts** (e.g. `macminim`): *unattended* push, plus `pull` and `ls` — the things croc can't do. `rsync` over SSH. |
| [`claude-ai-archive`](plugins/skillz/skills/claude-ai-archive/SKILL.md) | Import/sync a claude.ai data export into a local on-disk mirror (`~/CLAUDE.ai/`); recovers conversation→project mapping via browser-harness. |
| [`sprite`](plugins/skillz/skills/sprite/SKILL.md) | Sprite ([sprites.dev](https://sprites.dev/)) VM environment agent: services, checkpoints/restores, dev servers, and network policy via the in-VM `sprite-env` CLI. |
| [`sprite-api-gateway`](plugins/skillz/skills/sprite-api-gateway/SKILL.md) | Access external APIs (GitHub, Slack, Linear, …) from a Sprite through the authenticated `api.sprites.dev` gateway — no raw API keys. |
| [`test-on-sprite`](plugins/skillz/skills/test-on-sprite/SKILL.md) | Test a repo in a disposable Sprite VM: provision a sprite per target, authenticate Claude + GitHub, checkpoint a reset point, then clone at a branch and run install/tests — driven through a live herdr console pane. |
| [`herdr`](plugins/skillz/skills/herdr/SKILL.md) | Control herdr (terminal-native agent multiplexer) from inside it. **Modified fork** of herdr's own skill (AGPL-3.0) with corrected pane self-identification. See [License](#license). |

> **Two transfer skills — which fires?** Default is **`croc`**. **`file-transfer`**
> takes over only when the target is a named SSH host (e.g. `macminim`), when
> pulling *from* a remote, listing a remote directory, or running an unattended /
> scripted sync. Those are precisely what croc can't do: it is push-only and needs
> a person at the far end to enter the code phrase.

### file-transfer

The **SSH specialist** — use it when `croc` can't do the job (unattended push,
`pull`, `ls`, scripted sync); otherwise `croc` is the default.

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

### croc

The **default transfer skill** — reach for this unless one of the
`file-transfer` conditions above applies.

Sends files, folders, or text between **any two computers** — even across
different networks, to a phone, or to a machine you have no SSH access to. Uses
[`croc`](https://github.com/schollz/croc): the two sides agree on a short
**code phrase**, which drives a PAKE key exchange, and the data flows
**end-to-end encrypted** through a relay. No port-forwarding, no server to run
(a public relay is built in), no accounts.

```bash
croc send <file-or-folder>              # prints a code phrase, then waits
croc send --text "a note or URL"        # send text instead of a file

CROC_SECRET=<code-phrase> croc          # receive — Linux/macOS
croc --yes <code-phrase>                # receive — Windows (flags before the code)
```

In practice you just ask Claude Code *"send report.pdf with croc"* or *"receive
croc code 8451-…"* and the skill fires. It also covers the security model (the
code phrase **is** the credential — let croc generate a random one, treat it as
one-time), self-hosting a relay, and the flags for excludes, QR codes, proxies,
and piping.

It's opinionated about the traps that make croc **silently no-op**: on
Linux/macOS the code must travel via `CROC_SECRET` rather than argv (when
receiving *and* when sending with a custom code) or croc just prints guidance and
exits 0; global flags must precede the code positional; piping a received file
needs `--stdout`; and a password-protected relay must be *started* with the same
`--pass` its clients use.

Its one limitation: a **person must be at the far end** to run the receive
command, and both ends must be live at the same time. When that's a problem — an
unattended push to `macminim`, a `pull`, an `ls`, or a scripted sync — use
**file-transfer** instead.

**Prerequisites:** `croc` on `$PATH` on both machines (`brew install croc`, or
`curl https://getcroc.schollz.com | bash`).

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
