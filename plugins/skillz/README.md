# skillz (plugin)

The plugin bundle for the [`skillz`](../../README.md) marketplace. Skills live
under `skills/<name>/SKILL.md`.

## Skills

- **file-transfer** — push/pull files to/from `macminim` (or any passwordless-SSH
  host) via rsync over SSH. See [`skills/file-transfer/SKILL.md`](skills/file-transfer/SKILL.md).
- **claude-ai-archive** — import/sync a claude.ai data export into a local
  on-disk mirror (`~/CLAUDE.ai/`), and recover conversation→project mapping via
  browser-harness. See [`skills/claude-ai-archive/SKILL.md`](skills/claude-ai-archive/SKILL.md).
- **sprite** — Sprite ([sprites.dev](https://sprites.dev/)) VM environment agent:
  manage services, checkpoints/restores, dev servers, and network policy via the
  in-VM `sprite-env` CLI. See [`skills/sprite/SKILL.md`](skills/sprite/SKILL.md).
- **sprite-api-gateway** — access external APIs (GitHub, Slack, Linear, …) from a
  Sprite through the authenticated `api.sprites.dev` gateway — no raw keys.
  See [`skills/sprite-api-gateway/SKILL.md`](skills/sprite-api-gateway/SKILL.md).
