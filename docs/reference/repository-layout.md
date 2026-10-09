# Repository layout

```text
skillz/
├── README.md                          # what, why, how; the skills index
├── AGENTS.md                          # for agents: install, verify, update, release
├── CHANGELOG.md
├── LICENSE                            # Apache-2.0 (full text)
├── NOTICE                             # copyright; third-party material (herdr, grilling)
├── release.sh                         # checks, then tags vX.Y.Z (maintainer)
├── .claude-plugin/
│   └── marketplace.json               # marketplace manifest -> lists the skillz plugin
├── docs/                              # tutorials/, guides/, reference/
├── examples/                          # 01-03, each with a README
├── tests/
│   ├── run-all.sh                     # offline checks; --live adds the Jev evals
│   └── docs-links.py                  # every relative link and anchor resolves
└── plugins/
    └── skillz/
        ├── .claude-plugin/
        │   └── plugin.json            # plugin manifest (name, version, author)
        ├── LICENSE                    # Apache-2.0, the root's text (ships with the plugin)
        ├── NOTICE                     # the root's NOTICE (ships with the plugin)
        ├── README.md
        ├── hooks/
        │   └── hooks.json             # the reflex procedures hook (a no-op unless opted in)
        └── skills/                    # one folder per skill
            ├── reflex/
            │   ├── SKILL.md           # both engines: jev (procedures) and prompt (REFLEXES.md)
            │   ├── scripts/
            │   │   ├── hook.sh        # hook entry: exits at once unless procedures/config.json exists
            │   │   └── dispatch.py    # asks Jev, injects steps; test/eval/list/log/check
            │   └── tests/
            │       └── test_dispatch.py   # against a mock Jev; no network
            ├── file-transfer/
            │   ├── SKILL.md
            │   └── scripts/transfer.sh
            ├── claude-ai-archive/     # SKILL.md, config.json, lib/, scripts/
            ├── herdr/                 # MODIFIED fork of herdr's skill; LICENSE beside it (AGPL-3.0-or-later)
            ├── sdlc-jev/              # SKILL.md, gates.json, scripts/gate.py
            └── ...                    # one folder per remaining skill
```

- **`marketplace.json`** advertises one plugin, `skillz`, sourced from
  `./plugins/skillz`.
- **`plugin.json`** is the plugin's manifest. Skills are found in `skills/` and
  hooks in `hooks/hooks.json` by Claude Code's default paths; neither is listed in
  the manifest.
