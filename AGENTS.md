# AGENTS.md -- installing, operating and releasing skillz

For an agent (Claude Code, Codex, Gemini CLI, OpenCode, ...) asked to install,
verify, update, uninstall or release skillz. Each step has the command and how to
tell it worked. The human docs are linked, not repeated.

## Safety rules

- **Never handle secret values.** No keys or passwords in commands, files, logs
  or chat. The TypeSafe key is used by reference (`with-secret`,
  `keychain:typesafe`) or from the environment. If one is missing, ask the human
  to store it (`with-secret --store typesafe`); never ask for the value.
- **Never set up reflex procedures without the human's yes.** They send the text
  of eligible events to TypeSafe. Check the config dir's data rules first
  (CLAUDE.md, CLAUDE.local.md); if they forbid sending session content to a third
  party, do not set it up.
- **Ask first** before deleting a procedure, `REFLEXES.md`, or anything in a
  config dir, and before changing permissions.

## Prerequisites

| Need | Detect | For |
|---|---|---|
| Claude Code with plugins | `claude plugin --help` lists `marketplace` | everything |
| python3 | `python3 --version` | reflex procedures, several skills' scripts |
| a TypeSafe API key | `with-secret --check TYPESAFE_API_KEY=keychain:typesafe`, or `TYPESAFE_API_KEY` set | reflex procedures, sdlc-jev |
| jq | `jq --version` | the docs' shell snippets |

## Install

```zsh
claude plugin marketplace add ramazanpolat/skillz
claude plugin install skillz@skillz
```

**Verify:** `claude plugin list` shows `skillz@skillz` enabled. In a session,
`/skillz:reflex list` answers. Details: [docs/guides/install-update-uninstall.md](docs/guides/install-update-uninstall.md).

## Verify reflex procedures (only where set up)

```zsh
C="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
D="$(jq -r '.plugins["skillz@skillz"][0].installPath' "$C/plugins/installed_plugins.json")/skills/reflex/scripts/dispatch.py"
python3 "$D" check      # config, procedures, key, one live call; exit 0
python3 "$D" list       # no BROKEN lines
```

## Update

```zsh
claude plugin marketplace update skillz
claude plugin update skillz@skillz
```

**Verify:** `claude plugin list` shows the new version. Procedures and
`REFLEXES.md` are in the config dir and are not touched.

## Uninstall

```zsh
claude plugin uninstall skillz@skillz
claude plugin marketplace remove skillz
```

**Verify:** `claude plugin list` no longer shows it. `procedures/` and
`REFLEXES.md` stay until the human removes them.

## Before any release

The rule, verbatim:

> Before any release (tag, GitHub release, marketplace version) of any repo you work on, it must have: a README (what/why/how, short), docs/ with tutorials and guides for common operations, examples/ from smallest to full-blown each with its own README, and an AGENTS.md for installation/deployment. If any is missing, build it first or tell the pilot; never release without it.

Checklist for this repo (`release.sh` checks items 1-6 and refuses to tag otherwise):

1. `README.md` is present, with its four parts (what, why, how, where next), and at most ~120 lines.
2. `docs/README.md`, and at least one page each in `docs/tutorials/`, `docs/guides/` and `docs/reference/`.
3. `examples/README.md`, and a `README.md` in every `examples/NN-*/`.
4. `AGENTS.md` is present, with this section.
5. `plugin.json` `version` and `marketplace.json` `metadata.version` both equal the tag, and `CHANGELOG.md` has its `## [vX.Y.Z]` entry.
6. `tests/run-all.sh` passes: unit tests, docs links, manifests, shellcheck.
7. With a key: `tests/run-all.sh --live` passes (the procedure-set evals against Jev).

Then, on `main`, `./release.sh vX.Y.Z`. Only the maintainer, or the agent the
human authorized, runs it. [docs/guides/release.md](docs/guides/release.md).

## Where to report failures

The failing command, its exit code and last lines; `claude --version`; the
plugin version; for procedures, `dispatch.py check` and `dispatch.py log 20`.
Open an issue at https://github.com/ramazanpolat/skillz/issues, or tell the human.
