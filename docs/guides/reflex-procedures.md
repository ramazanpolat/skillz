# Keep standing procedures with Jev

Operations for the `reflex` skill's **jev engine**: set it up, add and tune a
procedure, test it, read what it did, pause or remove it, move entries over from
`REFLEXES.md`. Every one of these can be asked of Claude in plain words; the
commands below are what the skill runs. Exact behaviour:
[reference/procedures.md](../reference/procedures.md).

In the commands, `D` is the dispatcher of the installed plugin:

```zsh
C="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
D="$(jq -r '.plugins["skillz@skillz"][0].installPath' "$C/plugins/installed_plugins.json")/skills/reflex/scripts/dispatch.py"
```

## Set it up

Ask: `/skillz:reflex setup jev`. The skill:

1. checks your config's data rules (CLAUDE.md, CLAUDE.local.md) and stops if they
   forbid sending session content to a third party;
2. tells you what leaves the machine: the text of every **eligible** event goes to
   `api.typesafe.ai`, clipped and redacted, best effort;
3. finds the key by reference (`with-secret --check TYPESAFE_API_KEY=keychain:typesafe`),
   or asks you to store it yourself with `with-secret --store typesafe`, never
   asking for the value;
4. writes `<config>/procedures/config.json` and runs `python3 "$D" check`.

A config dir without `procedures/config.json` is untouched: the hook exits in
a few milliseconds.

## Add a procedure

Ask for it the way you would say it: "from now on, whenever I'm about to open a
PR, request Codex once and read the head back before reporting it." The skill
drafts the file, then **tunes it before writing**: three events that must fire,
three near-misses that must not, evaluated against Jev in a scratch directory.
You see the draft, the result and which event kinds will now reach TypeSafe. On
your yes it writes `procedures/<name>.md` and keeps the events in
`procedures/evals/<name>.json`.

Tuning is where most of the quality comes from. Jev reads literally: `git tag` in
`covers` also matches `git tag -l`, until `excludes` says listing tags does not
count. Fix the wording; never lower `fire` to make a case pass.

## Test one event

```zsh
python3 "$D" test bash "gh pr create --title demo"
python3 "$D" test user_prompt "why did you tag it?"
python3 "$D" test reply "Head is 5b5d8e9, MERGEABLE."
```

A dry run: it prints the eligible procedures, Jev's choice and probability, and
what would happen. Nothing is injected, logged or remembered.

## Re-run a procedure's evals

```zsh
python3 "$D" eval "$C/procedures/evals/open-pr.json"
```

Exit 0 only if every event is decided as expected. Run it after editing a
procedure, and after adding one whose kinds overlap it.

## See what fired

```zsh
python3 "$D" list        # status, mode, fires, kinds; broken files
python3 "$D" log 30      # the last 30 decisions
```

Judge a procedure by what its steps produced, not by the log: `fire` means Jev
matched and the steps were injected, not that they were followed.

## Pause, resume, remove

Ask: `pause open-pr`, `resume open-pr`, `remove open-pr`. Pause and resume flip
`status:` in the file. Remove shows the file, offers pause instead if it has
fired, and pastes the file into the reply before deleting it.

## Move entries over from REFLEXES.md

Ask: `/skillz:reflex migrate`. Each entry whose stimulus an event carries
becomes a procedure, tuned like a new one. Entries about a session starting or
time passing stay in `REFLEXES.md`. When none are left, the `@REFLEXES.md`
import is removed and the file kept as `REFLEXES.md.migrated`.

## Turn it off

Delete or rename `procedures/config.json`, or set `"engine": "off"`. The
procedures stay; the hook stops at once.

## Troubleshooting

| Symptom | Check |
|---|---|
| nothing ever fires | `python3 "$D" check`: config, key, one live call. `python3 "$D" log`: are events arriving at all? |
| `action: error` in the log | the error field: a timeout (raise `timeout_s`), 401 (the key), unreachable network |
| fires on the wrong events | `python3 "$D" test` the event; add the near-miss to `excludes` and re-run the evals |
| never fires on a real case | is its kind in `fires_on`? `test` it; make `covers` name that case |
| a file is ignored | `python3 "$D" list` shows it as `BROKEN` with the reason |
