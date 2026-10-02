# 01 -- Install skillz and use a skill

About five minutes. You need Claude Code.

## Install

In a Claude Code session:

```text
/plugin marketplace add ramazanpolat/skillz
/plugin install skillz@skillz
```

The first line registers this repository as a marketplace; the second installs
the `skillz` plugin with every skill in it. Run `/plugin` and check that
`skillz` is listed and enabled.

## Use a skill without naming it

Skills fire on their description. Ask for something one of them covers:

```text
take a step back: we've tried three fixes for this flaky test and none held
```

The `step-back` skill loads (Claude says so), and the answer follows its shape:
the goal apart from the method, the assumption keeping you stuck, genuinely
different approaches, and the smallest test to run first.

## Call a skill by name

Every skill is also a command under the plugin's name:

```text
/skillz:reflex list
```

On a fresh install that reports no reflexes yet; the next tutorial adds one.

## What you did

- Installed a marketplace and its one plugin.
- Saw a skill chosen from its description, and one called by name.

Next: [02 -- Your first procedure](02-your-first-procedure.md).
