---
name: test-on-sprite
description: Use this skill to test a repo in a disposable, isolated Sprite VM (sprites.dev) instead of on the host — provisioning a sprite per target, authenticating Claude and GitHub interactively, checkpointing a clean reset point, then cloning the target at a branch and running its install + tests. Use when the user wants to test a playbook/installer/app in a throwaway environment, "test on sprite", or run a target's suite without touching their real config. Drives a live herdr console pane per target.
---

Test a target repo inside a **Sprite VM** — an isolated, disposable environment — so installers and suites never touch the host's `~/.zshrc`, real config dirs, or running panes. Each target gets its own sprite with a fast checkpoint reset point.

Builds on the sibling `sprite` and `sprite-api-gateway` skills. Requires: the `sprite` CLI (host) and `herdr` (this session runs inside a herdr pane).

## Model

Two phases:
- **Provision** (once per sprite): create sprite → authenticate Claude → checkpoint → authenticate GitHub → checkpoint (the **ready** reset point). Auth steps are interactive — the user does them in a live herdr console pane.
- **Test run** (repeatable, fast): optionally restore the ready checkpoint → clone the target at a branch → install → run tests → capture a log.

All machine/repo specifics live in a **gitignored config** at `${XDG_CONFIG_HOME:-~/.config}/test-on-sprite/config.json` (resolved on first use, never committed). The skill and scripts stay generic. See `config.example.json` for the shape.

Scripts live in `scripts/` (`provision.sh`, `run-tests.sh`, `lib.sh`).

## Provisioning a target

1. **Resolve config.** If `provision.sh ensure <target>` reports no `repo_url`, ask the user for the repo URL, branch, install command, and test command. Auto-suggest `repo_url`/`branch` from a local clone's `git remote get-url origin` and current branch if the user points at one. Then:

   ```bash
   scripts/provision.sh ensure <target> \
     --repo-url <url> --branch <branch> \
     --install-cmd '<install>' --test-cmd '<test>'
   ```

   This seeds config, creates-or-reuses the sprite (`test-<target>` by default), opens a **herdr console pane to the right** running `sprite console -s <sprite>`, and prints the sprite's **network egress policy**. Review that policy: `github.com` and the Claude/GitHub auth endpoints must be reachable, or auth/clone will fail.

2. **Authenticate Claude** in the console pane. Tell the user to run `claude` there and complete login. Verify with `herdr pane read <pane>`, then:

   ```bash
   scripts/provision.sh checkpoint <target> claude-auth
   ```

3. **Authenticate GitHub** in the pane: `gh auth login --git-protocol https --web`. The user completes the web/device flow; verify `gh auth status`. This gives the git credential helper for cloning (incl. private repos). Then snapshot the **ready** reset point:

   ```bash
   scripts/provision.sh checkpoint <target> ready
   ```

   The new checkpoint id is saved as `ready_checkpoint` in config.

You can drive the interactive steps with `herdr pane send-text <pane> '<cmd>'` + `send-keys <pane> Enter`, and watch with `herdr pane read <pane>`. Never use `herdr pane split --current` — split off `$HERDR_PANE_ID` explicitly (it otherwise lands in the wrong tab).

## Running tests

```bash
scripts/run-tests.sh <target> [--restore|--no-restore] [--branch <b>]
```

- `--restore` restores the ready checkpoint first for a clean slate. **It is destructive** (drops the sprite's current session) — confirm with the user before passing it. Default is `--no-restore`.
- Steps: clone `<branch>` → run `install_cmd` → run `test_cmd` (skipped if empty), each from the clone dir inside the sprite. Output is teed to `${XDG_CONFIG_HOME:-~/.config}/test-on-sprite/logs/test-on-sprite-<target>-<ts>.log`; the script prints the log path and exits non-zero on any step failure.
- For richer, suite-driven targets whose tests are defined in an in-repo `TESTS.md` (e.g. the kommander/claude playbooks), run the individual suite commands live in the console pane and read results, rather than a single `test_cmd`. Copy the captured log into the active task's `artifacts/` if one is in progress.

## Caveats (check these when something fails)

- **Network policy** is the most common breakage: a sprite only reaches allowed domains (`/.sprite/policy/network.json`). If clone or `gh`/`claude` auth fails, inspect the policy and tell the user which domain to allow.
- **cmux/herdr-driven tests don't run inside a sprite** — there's no cmux/herdr in the VM. Run only the non-interactive suites in-sprite and tell the user which suites were skipped (don't report a partial run as full coverage).
- **Claude auth is interactive** by design — don't try to automate the login.
- One sprite/pane per target; re-running `ensure` reuses an existing sprite and just reopens a pane.
