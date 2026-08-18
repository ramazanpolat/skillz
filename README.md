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
| [`reflex`](plugins/skillz/skills/reflex/SKILL.md) | Standing "whenever X happens, do Y" instructions that fire on their own in later sessions — model-evaluated entries kept in a `REFLEXES.md` that `CLAUDE.md` imports, so they are in the prompt from the first turn. |
| [`whetstone`](plugins/skillz/skills/whetstone/SKILL.md) | Adversarial cross-agent review loop: open a PR, have Codex review it, fix **every** finding, re-request, repeat — and merge only on a round that returns clean. |
| [`grilling`](plugins/skillz/skills/grilling/SKILL.md) | Interview the user relentlessly about a plan, decision, or idea — round-by-round design-tree questioning — to stress-test their thinking before acting on it. Imported from [mattpocock/skills](https://github.com/mattpocock/skills) (MIT). |
| [`sbx`](plugins/skillz/skills/sbx/SKILL.md) | Run an agent — or a plain shell — inside a [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/) microVM (own kernel, filesystem, Docker daemon, deny-by-default network) via the `sbx` CLI: lifecycle, `--clone` workspaces, network policy, secrets, ports, templates, kits — plus [test-bench recipes](plugins/skillz/skills/sbx/references/test-arena.md) for using sandboxes as a disposable scenario harness. |
| [`living-docs`](plugins/skillz/skills/living-docs/SKILL.md) | Keep a repo's living documents in the root and retire stale ones into `history/` — one accepted version per doc, drafts beside it, nothing deleted. Set up the convention, retire a superseded doc, promote a draft, or show what is live vs retired. |

> **Two transfer skills — which fires?** Default is **`croc`**. **`file-transfer`**
> takes over only when a **named passwordless-SSH host** (e.g. `macminim`) is
> involved — that is a precondition, not one trigger among several, because the
> skill only speaks rsync-over-ssh. Given such a host it does what croc can't:
> unattended transfer with nobody at the far end, pulling *from* that host, listing
> a directory on it, or a scripted sync that skips unchanged files. When the other
> end is a **service** rather than a person or an SSH host — a URL, a git remote, a
> package registry, an artifact store, a cloud bucket — it is neither skill's job,
> uploading or downloading alike.

### file-transfer

The **SSH specialist** — it needs a named passwordless-SSH host; given one, use it
for what `croc` can't do (unattended push, `pull` from that host, `ls` on it,
scripted sync). Otherwise `croc` is the default.

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

### test-on-sprite

Runs a target repo's installer and suite inside a **Sprite VM** ([sprites.dev](https://sprites.dev/))
rather than on the host, so an installer can rewrite `~/.zshrc` or a real config
directory without consequence. Two phases: **provision** once per sprite (create,
authenticate Claude, checkpoint, authenticate GitHub, checkpoint again — that
second one is the *ready* reset point), then **test runs** that are fast and
repeatable (restore ready, clone at a branch, install, test, capture a log).
Interactive auth happens in a live herdr console pane. Machine and repo
specifics live in a config outside any repo
(`${XDG_CONFIG_HOME:-~/.config}/test-on-sprite/config.json`) — the skill and its
`scripts/` stay generic, and `config.example.json` documents the shape.

### reflex

Standing "whenever X happens, do Y" instructions that fire on their own in later
sessions. Reflexes are **model-evaluated** — nothing polls, nothing watches a
file. Every active entry is imported into the system prompt and matched against
what actually happens in the session.

That import is the whole mechanism, and it is why a skill alone cannot do this: a
skill's body is not in context until it is invoked, so nothing would be watching.
Entries live in one `REFLEXES.md` that `CLAUDE.md` imports with `@` — one literal
filename, because `@dir/` and `@dir/*.md` bring in no content — which is also why
there is no compile step and no per-entry file. The skill covers the traps: the
config directory must be resolved (`${CLAUDE_CONFIG_DIR:-$HOME/.claude}`), never
assumed; the import must never be added before the file exists, or the raw
`@REFLEXES.md` line sits in the prompt reading as a missing instruction set; and
a `REFLEXES.md` that arrives with entries but no firing rules is silently inert.

### whetstone

A development model, not a tool: **sharpen a change against a second agent until no
burr remains.** Open a PR, have Codex review it, fix *every* finding, re-request the
review, and repeat — merging only on a round that returns **zero findings on the
current head commit**. "Looks fine" is not the criterion.

```text
open PR ──> @codex review ──> fix ALL findings ──> re-request
                ^                                       |
                └──────────── not clean ────────────────┘
                                  |
                                clean
                                  v
                                merge
```

The value is that the reviewer is not the author. In the campaign this skill was
distilled from — 20 rounds, 32 findings, every one a real defect — six rounds found
defects *in the fix written for the previous round*, and one found an error being
swallowed by code written to stop swallowing errors. Nearly every finding was in
something the author had just convinced themselves was correct.

The skill covers the parts that are easy to get wrong: writing wrong-claim criteria
into the PR body so the review has something to aim at, verifying a fix by
reproducing the failure first and testing both directions, and the fact that findings
arrive as PR *reviews* while the clean verdict arrives as a plain *issue* comment — so
a watcher looking only at reviews times out on success and looks like nothing
happened.

### grilling

Stress-tests a plan, decision, or idea by interviewing the user round by round.
Claude maps the problem as a **design tree** — every decision branches into the
decisions that hang off it — and works the **frontier**: every question whose
prerequisites are already settled, asked all at once with a recommended answer,
never blocking on facts a sub-agent could look up instead. The session ends only
when the frontier is empty — every branch visited, nothing silently assumed.

Fires on "grill me on this," "stress-test this plan," or similar trigger phrases.

> Imported as-is from [mattpocock/skills](https://github.com/mattpocock/skills),
> licensed MIT. No modifications; see [License](#license).

### living-docs

A document-lifecycle convention for repos whose important documents evolve: **the
root holds what is true now, `history/` holds what used to be true.** Exactly one
accepted version of each document lives in the root, drafts sit *beside* it
rather than on top of it, and superseded versions are moved aside — never
deleted, because a retired document is a browsable record of why a decision was
made while a deleted one is buried in history nobody reads.

Two rules carry most of the weight: a current version **never refers back** to
what it replaced (no "supersedes v2", no changelog paragraph — that story belongs
in the commit message), and `history/` is **read-only**, never repointed or
corrected, since its whole value is being accurate about what was believed at the
time.

Performs four operations — `init` (create `history/`, add the convention block to
the repo's `CLAUDE.md`), `retire` (`git mv` a superseded doc, then repoint the
live documents that referenced it), `accept` (promote a draft, retire what it
replaces), and `status` (what is live vs retired). Document-type agnostic:
`DESIGN.md`, `SPEC-v*.md`, `RFC-*.md`, `PLAN-*.md`.

### sbx

Wraps the [`sbx`](https://docs.docker.com/reference/cli/sbx/) CLI — Docker
Sandboxes — so untrusted or destructive work runs in a **microVM** instead of on
the host: separate kernel, own filesystem, own Docker daemon, deny-by-default
egress proxied through the host. Covers the lifecycle (`run` / `create` / `ls` /
`exec` / `stop` / `rm`), the direct-vs-`--clone` workspace choice and the
`sandbox-<name>` git remote clone mode leaves behind, network policy presets and
per-sandbox allow/deny rules, host-side secret injection (the raw key never
enters the VM), published ports, `cp`, templates, kits, and MCP.

The parts that actually bite are called out: creation-time-only flags that are
silently ignored on re-attach, `sbx policy check network <host>` before debugging
a "broken" tool inside the sandbox, direct mode not protecting the host from git
hooks and `package.json` scripts it later runs itself, and `sbx reset` being a
sign-you-out, delete-everything button.

A companion file,
[`references/test-arena.md`](plugins/skillz/skills/sbx/references/test-arena.md),
turns the same feature set into a **test-bench cookbook**: headless CI bootstrap,
one disposable bench per scenario, oracle (no-LLM) runs on the `shell` agent,
driving a real agent at a pty, reality-based assertions and artifact extraction,
telemetry egress via `host.docker.internal`, chaos by network denial, a nested
compose stack inside the bench's own Docker daemon, parallel matrices with a
budget guard, pre-warmed template images, per-subject kits — and an executable
credential-isolation test for the "use-but-not-read" claim. Ends with a
feature→placement map and an explicit list of what is documented versus what
still needs verifying on a signed-in host.

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

This repository also bundles, unmodified, the `grilling` skill from
[mattpocock/skills](https://github.com/mattpocock/skills)
(`plugins/skillz/skills/grilling/`), Copyright (c) 2026 Matt Pocock, licensed
MIT. MIT permits redistribution under AGPL-3.0-or-later; see [`NOTICE`](NOTICE).
