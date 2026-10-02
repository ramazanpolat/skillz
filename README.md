# skillz

## What it is

A collection of [Claude Code](https://claude.com/claude-code) **skills**,
packaged as one plugin in a plugin marketplace, so every skill installs with
one command. A skill is a folder with a `SKILL.md`: Claude reads its
description and uses it when a request matches, then follows its instructions
and scripts. The bundle also ships one hook, for the `reflex` skill's
procedures; it does nothing unless you set procedures up.

## Why it exists

Some work repeats with the same traps every time: moving files to a particular
host, archiving claude.ai exports, driving a VM or a sandbox, reviewing a PR
until it comes back clean, keeping standing rules that fire on their own. A
skill writes the procedure down once, with the traps, so every session does it
the same way. Keeping them in one repository keeps them versioned, reviewed and
installable together.

## How it is used

```text
/plugin marketplace add ramazanpolat/skillz
/plugin install skillz@skillz
```

Verify with `/plugin`: the `skillz` plugin and its skills are listed. From then
on, ask for the work in plain words ("send this folder to my laptop", "take a
step back", "from now on, whenever I open a PR, ..."), or call a skill by name
(`/skillz:reflex list`).

### The skills

| Skill | What it does |
|-------|--------------|
| [`croc`](plugins/skillz/skills/croc/SKILL.md) | **Default for sending.** Files, folders, or text to **any** computer (no SSH needed) with [`croc`](https://github.com/schollz/croc) — peer-to-peer, end-to-end encrypted via a one-time code phrase; no server, no accounts. |
| [`file-transfer`](plugins/skillz/skills/file-transfer/SKILL.md) | Specialist for **passwordless-SSH hosts** (e.g. `macminim`): *unattended* push, plus `pull` and `ls` — the things croc can't do. `rsync` over SSH. |
| [`claude-ai-archive`](plugins/skillz/skills/claude-ai-archive/SKILL.md) | Import/sync a claude.ai data export into a local on-disk mirror (`~/CLAUDE.ai/`); recovers conversation→project mapping via browser-harness. |
| [`sprite`](plugins/skillz/skills/sprite/SKILL.md) | Sprite ([sprites.dev](https://sprites.dev/)) VM environment agent: services, checkpoints/restores, dev servers, and network policy via the in-VM `sprite-env` CLI. |
| [`sprite-api-gateway`](plugins/skillz/skills/sprite-api-gateway/SKILL.md) | Access external APIs (GitHub, Slack, Linear, …) from a Sprite through the authenticated `api.sprites.dev` gateway — no raw API keys. |
| [`test-on-sprite`](plugins/skillz/skills/test-on-sprite/SKILL.md) | Test a repo in a disposable Sprite VM: provision a sprite per target, authenticate Claude + GitHub, checkpoint a reset point, then clone at a branch and run install/tests — driven through a live herdr console pane. |
| [`herdr`](plugins/skillz/skills/herdr/SKILL.md) | Control herdr (terminal-native agent multiplexer) from inside it. **Modified fork** of herdr's own skill (AGPL-3.0) with corrected pane self-identification. See [License](#license). |
| [`reflex`](plugins/skillz/skills/reflex/SKILL.md) | Standing "whenever X happens, do Y" instructions that fire on their own. **jev engine:** each is a procedure file, and a hook asks TypeSafe's Jev on every eligible event whether one applies, then injects its steps; nothing sits in the prompt. **prompt engine:** entries in a `REFLEXES.md` that `CLAUDE.md` imports. |
| [`whetstone`](plugins/skillz/skills/whetstone/SKILL.md) | Adversarial cross-agent review loop: open a PR, have Codex review it, fix **every** finding, re-request, repeat — and merge only on a round that returns clean. |
| [`grilling`](plugins/skillz/skills/grilling/SKILL.md) | Interview the user relentlessly about a plan, decision, or idea — round-by-round design-tree questioning — to stress-test their thinking before acting on it. Imported from [mattpocock/skills](https://github.com/mattpocock/skills) (MIT). |
| [`sbx`](plugins/skillz/skills/sbx/SKILL.md) | Run an agent — or a plain shell — inside a [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/) microVM (own kernel, filesystem, Docker daemon, deny-by-default network) via the `sbx` CLI: lifecycle, `--clone` workspaces, network policy, secrets, ports, templates, kits — plus [test-bench recipes](plugins/skillz/skills/sbx/references/test-arena.md) for using sandboxes as a disposable scenario harness. |
| [`living-docs`](plugins/skillz/skills/living-docs/SKILL.md) | Keep a repo's living documents in the root and retire stale ones into `history/` — one accepted version per doc, drafts beside it, nothing deleted. Set up the convention, retire a superseded doc, promote a draft, or show what is live vs retired. |
| [`step-back`](plugins/skillz/skills/step-back/SKILL.md) | Reframe a stuck problem: separate the intended outcome from the current method, name the untested assumption that makes the failing approach look necessary, compare genuinely different alternatives, and propose the smallest reversible test. Fires on "take a step back", "what are we doing wrong", "take a deep breath". |
| [`sdlc`](plugins/skillz/skills/sdlc/SKILL.md) | An AI-native SDLC for a repo: six stages (Plan, Design, Build, Test, Deploy, Maintain), the artifact each produces (`intent.md`, `spec.md`, `plan.md`, proof in the report, `REVIEW.md`, `bands.yaml`), and the human gate each must pass. Encodes [Anthropic's AI-native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook) as an executable repo-local skill. |
| [`sdlc-jev`](plugins/skillz/skills/sdlc-jev/SKILL.md) | Screen an SDLC artifact against its gate criteria **before** a human reviews it, using [TypeSafe](https://docs.typesafe.ai) System One (Jev) — typed judgments with calibrated probabilities instead of a reviewer's prose. Criteria and thresholds live in `gates.json`; it reports and **never approves**. ~$0.0008 per screening. |
| [`herdr-snapshot`](plugins/skillz/skills/herdr-snapshot/SKILL.md) | Save a herdr session's whole layout with the Kommander playbook, task and resumable session id behind each pane, and recreate it elsewhere with `claude --resume` fired into each pane — for bringing a fleet of agents back after a crash, OOM kill or reboot. No scripts: the agent runs the recipe live. |

## Where next

- [docs/](docs/README.md): tutorials, guides for common operations, and the reference (every skill in detail).
- [examples/](examples/README.md): runnable, from one reflex to a tuned set of procedures.
- [AGENTS.md](AGENTS.md): for an agent asked to install, verify, update or release skillz.
- [CHANGELOG.md](CHANGELOG.md)

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
