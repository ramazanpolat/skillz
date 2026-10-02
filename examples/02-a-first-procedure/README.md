# 02 -- A first procedure (the jev engine)

**Shows:** one procedure, `remote-kill`: before a command kills processes by
name pattern over ssh, the steps ("use a bracket pattern, or the ssh command
kills itself") reach the agent. Nothing of it is in the prompt; the hook asks
Jev when a shell command is about to run.

```
procedures/
    config.json              opt-in switch; key_ref names where the key is stored
    remote-kill.md           the trigger (covers, excludes, fires_on) and the steps
    evals/remote-kill.json   3 events that must fire, 3 near-misses that must not
```

**Needs:** python3, and a TypeSafe key: exported as `TYPESAFE_API_KEY`, or
stored for `with-secret` under the `key_ref` in `config.json`. The events' text is
sent to TypeSafe.

**Run it**, from the repository root:

```zsh
D=plugins/skillz/skills/reflex/scripts/dispatch.py
export REFLEX_PROCEDURES_DIR=examples/02-a-first-procedure/procedures
python3 $D list
python3 $D eval $REFLEX_PROCEDURES_DIR/evals/remote-kill.json
python3 $D test bash "ssh web1 'pkill -f gunicorn'"
```

**Expected:**

```
remote-kill              active auto fires=0    on=bash  Killing processes by pattern over ssh
...
6/6 as expected (fire threshold 0.8); Jev calls 6, median ~330 ms
eligible for bash: remote-kill
choice: remote-kill (p=1.00), ~330 ms -> fire
```

**To use it for real,** copy `config.json` and `remote-kill.md` into
`<config>/procedures/` (or ask `/skillz:reflex setup jev`, then describe the
rule). Clean up: nothing was written outside this directory.
