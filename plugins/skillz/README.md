# skillz (plugin)

The plugin bundle for the [`skillz`](../../README.md) marketplace. Skills live
under `skills/<name>/SKILL.md`.

## Skills

- **croc** — **the default for sending.** Files, folders, or text to **any**
  computer (no SSH needed) via [`croc`](https://github.com/schollz/croc):
  peer-to-peer, end-to-end encrypted through a one-time code phrase, no server
  and no accounts. Push-only, and needs a person at the far end.
  See [`skills/croc/SKILL.md`](skills/croc/SKILL.md).
- **file-transfer** — the **SSH specialist**, for what croc can't do: *unattended*
  push to a passwordless-SSH host (e.g. `macminim`), plus `pull` and `ls`, via
  rsync over SSH. See [`skills/file-transfer/SKILL.md`](skills/file-transfer/SKILL.md).
- **claude-ai-archive** — import/sync a claude.ai data export into a local
  on-disk mirror (`~/CLAUDE.ai/`), and recover conversation→project mapping via
  browser-harness. See [`skills/claude-ai-archive/SKILL.md`](skills/claude-ai-archive/SKILL.md).
- **sprite** — Sprite ([sprites.dev](https://sprites.dev/)) VM environment agent:
  manage services, checkpoints/restores, dev servers, and network policy via the
  in-VM `sprite-env` CLI. See [`skills/sprite/SKILL.md`](skills/sprite/SKILL.md).
- **sprite-api-gateway** — access external APIs (GitHub, Slack, Linear, …) from a
  Sprite through the authenticated `api.sprites.dev` gateway — no raw keys.
  See [`skills/sprite-api-gateway/SKILL.md`](skills/sprite-api-gateway/SKILL.md).
- **test-on-sprite** — test a repo in a disposable Sprite VM: provision a sprite per
  target, authenticate Claude + GitHub, checkpoint a clean reset point, then clone
  at a branch and run install/tests, driven through a live herdr console pane.
  See [`skills/test-on-sprite/SKILL.md`](skills/test-on-sprite/SKILL.md).
- **herdr** — control herdr (terminal-native agent multiplexer) from inside it.
  A **modified fork** of herdr's own skill (AGPL-3.0-or-later) with corrected pane
  self-identification (`$HERDR_PANE_ID` / `herdr pane current` instead of
  `focused` / `--current`). See [`skills/herdr/SKILL.md`](skills/herdr/SKILL.md)
  and the repo `NOTICE` / `LICENSE`.
