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
- **reflex** — standing "whenever X happens, do Y" instructions that fire on their
  own in later sessions. Model-evaluated: entries live in one `REFLEXES.md` that
  `CLAUDE.md` imports with `@`, so they are in the prompt from the first turn —
  nothing polls and nothing watches a file. See
  [`skills/reflex/SKILL.md`](skills/reflex/SKILL.md).
- **whetstone** — adversarial cross-agent review loop: open a PR, have Codex review
  it, fix **every** finding, re-request, repeat, and merge only on a round that
  returns clean. Covers wrong-claim criteria in the PR body, verifying a fix by
  reproducing the failure first, and the reviews-vs-issue-comments split that makes
  a clean round look like silence. See
  [`skills/whetstone/SKILL.md`](skills/whetstone/SKILL.md).
- **grilling** — interview the user relentlessly about a plan, decision, or idea:
  map it as a design tree, ask each round's frontier of settled-prerequisite
  questions with a recommended answer, and finish only once every branch is
  visited. Imported unmodified from
  [mattpocock/skills](https://github.com/mattpocock/skills) (MIT). See
  [`skills/grilling/SKILL.md`](skills/grilling/SKILL.md).
- **living-docs** — keep a repo's living documents in the root and retire
  superseded ones into `history/`: one accepted version per document, drafts
  beside it rather than on top, a current version that never refers back to what
  it replaced, and a read-only `history/`. Operations: `init`, `retire`,
  `accept`, `status`. See
  [`skills/living-docs/SKILL.md`](skills/living-docs/SKILL.md).
- **step-back** — reframe a stuck problem: separate the intended outcome from
  the current method, surface the untested assumption that makes the failing
  approach look necessary, compare two or three genuinely different approaches
  against the current baseline, and propose the smallest reversible test. Fires on
  "take a step back", "what are we doing wrong", "take a deep breath". See
  [`skills/step-back/SKILL.md`](skills/step-back/SKILL.md).
- **sbx** — run an agent, or a plain shell, inside a Docker Sandboxes microVM
  (own kernel, filesystem, Docker daemon, deny-by-default network) via the `sbx`
  CLI: sandbox lifecycle, direct-vs-`--clone` workspaces, network policy presets
  and rules, host-side secret injection, ports, `cp`, templates, kits, and MCP.
  See [`skills/sbx/SKILL.md`](skills/sbx/SKILL.md), plus
  [`skills/sbx/references/test-arena.md`](skills/sbx/references/test-arena.md) —
  worked recipes for using sandboxes as disposable test benches (headless CI,
  oracle runs, pty-driven agents, chaos by network denial, nested compose in the
  bench's own Docker daemon, and an executable credential-isolation test).
- **sdlc** — an AI-native SDLC for a repo: six stages (Plan, Design, Build, Test,
  Deploy, Maintain), the artifact each produces, and the human gate each must pass.
  Encodes [Anthropic's AI-native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook)
  as an executable skill. See [`skills/sdlc/SKILL.md`](skills/sdlc/SKILL.md).
- **sdlc-jev** — screen an SDLC artifact against its gate criteria *before* a human
  reviews it, via [TypeSafe](https://docs.typesafe.ai) System One (Jev): typed
  judgments with calibrated probabilities, criteria and thresholds in `gates.json`,
  exit codes for CI. Reports; **never approves**. See
  [`skills/sdlc-jev/SKILL.md`](skills/sdlc-jev/SKILL.md) and
  [`skills/sdlc-jev/gates.json`](skills/sdlc-jev/gates.json).
