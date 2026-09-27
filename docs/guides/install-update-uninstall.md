# Install, update, uninstall

## Install

```text
/plugin marketplace add ramazanpolat/skillz
/plugin install skillz@skillz
```

From a shell, for another config dir:

```zsh
CLAUDE_CONFIG_DIR=<dir> claude plugin marketplace add ramazanpolat/skillz
CLAUDE_CONFIG_DIR=<dir> claude plugin install skillz@skillz
```

Check: `/plugin` (or `claude plugin list`) shows `skillz@skillz`, enabled.

## Update

```zsh
claude plugin marketplace update skillz
claude plugin update skillz@skillz
```

Start a new session afterwards: skills and hooks are read at session start.
Your procedures and `REFLEXES.md` live in the config dir, not in the plugin, so
an update never touches them.

## Uninstall

```zsh
claude plugin uninstall skillz@skillz
claude plugin marketplace remove skillz
```

This removes the skills and the hook. It leaves what the skills wrote in your
config dir: `procedures/`, `REFLEXES.md` and its `@REFLEXES.md` import in
`CLAUDE.md`. Remove the import line yourself if you drop the prompt engine,
since a dangling `@` import stays in the prompt as a stray line.

## What the hook does on every install

The plugin registers one hook (for `reflex` procedures) on `UserPromptSubmit`,
`PreToolUse` (Bash, Write, Edit, MultiEdit, NotebookEdit, SendMessage) and
`Stop`. Without `<config>/procedures/config.json` it exits at once, having read
nothing and sent nothing.
