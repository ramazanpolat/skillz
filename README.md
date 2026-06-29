# skillz

Ramazan's personal collection of [Claude Code](https://claude.com/claude-code)
skills, distributed as a plugin marketplace so many skills can live in one repo.

## Install

```
/plugin marketplace add ramazanpolat/skillz
/plugin install skillz@skillz
```

That installs the `skillz` plugin and all skills it bundles. Claude will invoke
a skill automatically when a request matches its description; you can also list
them with `/plugin`.

## Skills

| Skill | What it does |
|-------|--------------|
| [`file-transfer`](plugins/skillz/skills/file-transfer/SKILL.md) | Push/pull files to/from the `macminim` Mac mini (or any passwordless-SSH host) via rsync over SSH. |

## Repo layout

```
skillz/
├── .claude-plugin/
│   └── marketplace.json        # marketplace entry → the skillz plugin
└── plugins/
    └── skillz/
        ├── .claude-plugin/
        │   └── plugin.json      # plugin manifest
        └── skills/
            └── file-transfer/   # one folder per skill
                ├── SKILL.md
                └── scripts/
```

## Adding a new skill

1. Create `plugins/skillz/skills/<new-skill>/SKILL.md` with YAML frontmatter
   (`name`, `description`) describing when Claude should use it.
2. Put any helper scripts under that skill's own `scripts/` folder.
3. Commit. Users get it on the next `/plugin update`.

No changes to `marketplace.json` or `plugin.json` are needed to add a skill —
skills are discovered from the `skills/` directory.
