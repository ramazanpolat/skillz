# Examples

From one standing rule in a file to a tuned set of procedures. Each directory has
a README: what it shows, what it needs, how to run it, and what you should see.
None of them touches your config dir unless you copy files into it yourself.

| # | Example | Shows | Needs |
|---|---|---|---|
| 01 | [a-first-reflex](01-a-first-reflex/) | a `REFLEXES.md` with one entry: the prompt engine | nothing |
| 02 | [a-first-procedure](02-a-first-procedure/) | one procedure file, its config and its evals: the jev engine | python3, a TypeSafe key |
| 03 | [procedure-set](03-procedure-set/) | seven procedures tuned together, with a dev set and a held-out set | python3, a TypeSafe key |

The dispatcher used below is `plugins/skillz/skills/reflex/scripts/dispatch.py`
in this repository (or the same path under the installed plugin).
