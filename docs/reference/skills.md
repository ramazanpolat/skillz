# The skills

One section per skill: what it does and what it needs. The one-line index is in the
[README](../../README.md#the-skills); the instructions Claude follows are each skill's own
`SKILL.md`.

> **Two transfer skills — which fires?** Default is **`croc`**. **`file-transfer`**
> takes over only when a **named passwordless-SSH host** (e.g. `macminim`) is
> involved — that is a precondition, not one trigger among several, because the
> skill only speaks rsync-over-ssh. Given such a host it does what croc can't:
> unattended transfer with nobody at the far end, pulling *from* that host, listing
> a directory on it, or a scripted sync that skips unchanged files. When the other
> end is a **service** rather than a person or an SSH host — a URL, a git remote, a
> package registry, an artifact store, a cloud bucket — it is neither skill's job,
> uploading or downloading alike.

### file-transfer

The **SSH specialist** — it needs a named passwordless-SSH host; given one, use it
for what `croc` can't do (unattended push, `pull` from that host, `ls` on it,
scripted sync). Otherwise `croc` is the default.

Moves files between your machine and a remote host that already accepts
**passwordless SSH** (key-based auth). Wraps `rsync -avz` over SSH, so transfers
are recursive, resumable, and skip unchanged files. Default host is `macminim`.

```bash
transfer.sh push <local-path> [remote-dest]   # local  -> remote (default dest: ~/)
transfer.sh pull <remote-path> [local-dest]   # remote -> local  (default dest: .)
transfer.sh ls   [remote-path]                # list a remote directory
```

Options: `-H/--host <alias>` (or `$SKILLZ_HOST`) to target another host,
`-n/--dry-run` to preview, `-h/--help` for full help.

Examples:

```bash
transfer.sh push ./report.pdf                # -> macminim:~/report.pdf
transfer.sh push ./build/ ~/deploys/app/     # trailing slash = copy CONTENTS
transfer.sh pull ~/logs/app.log ./logs/      # macminim -> ./logs/
transfer.sh -H macmini2 push ./data.csv      # different host
```

In practice you don't call the script by hand — just ask Claude Code something
like *"send report.pdf to macminim"* or *"pull ~/logs/app.log from macminim"* and
the skill fires.

**Prerequisites:** `ssh <host>` connects without a password (test:
`ssh -o BatchMode=yes macminim true`), and `rsync` is installed on both ends
(standard on macOS).

### croc

The **default transfer skill** — reach for this unless one of the
`file-transfer` conditions above applies.

Sends files, folders, or text between **any two computers** — even across
different networks, to a phone, or to a machine you have no SSH access to. Uses
[`croc`](https://github.com/schollz/croc): the two sides agree on a short
**code phrase**, which drives a PAKE key exchange, and the data flows
**end-to-end encrypted** through a relay. No port-forwarding, no server to run
(a public relay is built in), no accounts.

```bash
croc send <file-or-folder>              # prints a code phrase, then waits
croc send --text "a note or URL"        # send text instead of a file

CROC_SECRET=<code-phrase> croc          # receive — Linux/macOS
croc --yes <code-phrase>                # receive — Windows (flags before the code)
```

In practice you just ask Claude Code *"send report.pdf with croc"* or *"receive
croc code 8451-…"* and the skill fires. It also covers the security model (the
code phrase **is** the credential — let croc generate a random one, treat it as
one-time), self-hosting a relay, and the flags for excludes, QR codes, proxies,
and piping.

It's opinionated about the traps that make croc **silently no-op**: on
Linux/macOS the code must travel via `CROC_SECRET` rather than argv (when
receiving *and* when sending with a custom code) or croc just prints guidance and
exits 0; global flags must precede the code positional; piping a received file
needs `--stdout`; and a password-protected relay must be *started* with the same
`--pass` its clients use.

Its one limitation: a **person must be at the far end** to run the receive
command, and both ends must be live at the same time. When that's a problem — an
unattended push to `macminim`, a `pull`, an `ls`, or a scripted sync — use
**file-transfer** instead.

**Prerequisites:** `croc` on `$PATH` on both machines (`brew install croc`, or
`curl https://getcroc.schollz.com | bash`).

### claude-ai-archive

Keeps a local, greppable mirror of your claude.ai content at `~/CLAUDE.ai/` —
every chat as a `.md` + `.json` pair, every project as a folder you can `cd`
into. Takes a claude.ai **data export** (Settings → Account → Export data) and
builds or updates the archive; a browser-harness pass recovers the
conversation→project mapping the export omits.

```bash
# from the skill directory
python scripts/archive.py import --export <export.zip>   # first-time build
python scripts/archive.py sync   --export <export.zip>   # apply a newer export
browser-harness < scripts/harvest.py                     # recover project mapping
python scripts/archive.py refile                         # file chats into projects
python scripts/archive.py status                         # counts + sync state
```

In practice you just ask Claude Code *"import my claude.ai export"* or *"sync the
CLAUDE.ai archive"* and the skill fires. Archive root defaults to `~/CLAUDE.ai`
(override with `--archive-root` or `$CLAUDE_AI_ARCHIVE`).

**Prerequisites:** [`browser-harness`](https://github.com/) on `$PATH` and a
Chrome session logged into claude.ai (for the mapping pass), plus Python 3.

### herdr

Lets an agent control [herdr](https://github.com/ogulcancelik/herdr) — a
terminal-native agent multiplexer — from inside a herdr-managed pane: list/split
panes, run commands in siblings, wait for output or agent status, manage
workspaces and tabs. Active when `HERDR_ENV=1`.

> **This is a modified fork of herdr's own agent skill**, not original work.
> The upstream skill told agents *"the focused pane is yours,"* which is wrong
> when several agents run across workspaces — `focused: true` and the `--current`
> flag follow the **user's UI focus**, not the calling shell, so splits land in
> the wrong workspace. This fork teaches self-identification via `$HERDR_PANE_ID`
> and `herdr pane current` and passes explicit pane ids. herdr is licensed
> **AGPL-3.0-or-later**; this modified copy is redistributed under the same
> license with attribution — which is why this whole repo is AGPL (see
> [License](../../README.md#license)). Upstream: https://github.com/ogulcancelik/herdr.

### test-on-sprite

Runs a target repo's installer and suite inside a **Sprite VM** ([sprites.dev](https://sprites.dev/))
rather than on the host, so an installer can rewrite `~/.zshrc` or a real config
directory without consequence. Two phases: **provision** once per sprite (create,
authenticate Claude, checkpoint, authenticate GitHub, checkpoint again — that
second one is the *ready* reset point), then **test runs** that are fast and
repeatable (restore ready, clone at a branch, install, test, capture a log).
Interactive auth happens in a live herdr console pane. Machine and repo
specifics live in a config outside any repo
(`${XDG_CONFIG_HOME:-~/.config}/test-on-sprite/config.json`) — the skill and its
`scripts/` stay generic, and `config.example.json` documents the shape.

### reflex

Standing "whenever X happens, do Y" instructions that fire on their own in later
sessions, with two engines:

- **jev (procedures, v0.9.0).** Each instruction is a file in
  `<config>/procedures/`: the exact condition (`covers`, `excludes`), the event
  kinds it may fire on, and the steps. Nothing sits in the prompt. A plugin hook
  sends every eligible event (the user's message, a shell command, a file write
  or edit, an outgoing agent message, the final reply) to TypeSafe's Jev, which
  picks the procedure that applies, if any, with a calibrated probability; a
  confident match injects the steps at that moment, and a matching final reply
  is sent back once to be fixed. About 0.3 s per eligible event; opt-in per
  config dir; fails open. See [the procedures guide](../guides/reflex-procedures.md).
- **prompt (REFLEXES.md).** Entries live in one `REFLEXES.md` that `CLAUDE.md`
  imports with `@`, so they are in the prompt from the first turn and Claude
  matches them by its own judgment. No dependencies; every entry costs prompt
  tokens in every session. The skill covers the traps: the config directory must
  be resolved (`${CLAUDE_CONFIG_DIR:-$HOME/.claude}`), never assumed; the import
  must never be added before the file exists, or the raw `@REFLEXES.md` line sits
  in the prompt reading as a missing instruction set; and a `REFLEXES.md` that
  arrives with entries but no firing rules is silently inert.

### whetstone

A development model, not a tool: **sharpen a change against a second agent until no
burr remains.** Open a PR, have Codex review it, fix *every* finding, re-request the
review, and repeat — merging only on a round that returns **zero findings on the
current head commit**. "Looks fine" is not the criterion.

```text
open PR ──> @codex review ──> fix ALL findings ──> re-request
                ^                                       |
                └──────────── not clean ────────────────┘
                                  |
                                clean
                                  v
                                merge
```

The value is that the reviewer is not the author. In the campaign this skill was
distilled from — 20 rounds, 32 findings, every one a real defect — six rounds found
defects *in the fix written for the previous round*, and one found an error being
swallowed by code written to stop swallowing errors. Nearly every finding was in
something the author had just convinced themselves was correct.

The skill covers the parts that are easy to get wrong: writing wrong-claim criteria
into the PR body so the review has something to aim at, verifying a fix by
reproducing the failure first and testing both directions, and the fact that findings
arrive as PR *reviews* while the clean verdict arrives as a plain *issue* comment — so
a watcher looking only at reviews times out on success and looks like nothing
happened.

### grilling

Stress-tests a plan, decision, or idea by interviewing the user round by round.
Claude maps the problem as a **design tree** — every decision branches into the
decisions that hang off it — and works the **frontier**: every question whose
prerequisites are already settled, asked all at once with a recommended answer,
never blocking on facts a sub-agent could look up instead. The session ends only
when the frontier is empty — every branch visited, nothing silently assumed.

Fires on "grill me on this," "stress-test this plan," or similar trigger phrases.

> Imported as-is from [mattpocock/skills](https://github.com/mattpocock/skills),
> licensed MIT. No modifications; see [License](../../README.md#license).

### living-docs

A document-lifecycle convention for repos whose important documents evolve: **the
root holds what is true now, `history/` holds what used to be true.** Exactly one
accepted version of each document lives in the root, drafts sit *beside* it
rather than on top of it, and superseded versions are moved aside — never
deleted, because a retired document is a browsable record of why a decision was
made while a deleted one is buried in history nobody reads.

Two rules carry most of the weight: a current version **never refers back** to
what it replaced (no "supersedes v2", no changelog paragraph — that story belongs
in the commit message), and `history/` is **read-only**, never repointed or
corrected, since its whole value is being accurate about what was believed at the
time.

Performs four operations — `init` (create `history/`, add the convention block to
the repo's `CLAUDE.md`), `retire` (`git mv` a superseded doc, then repoint the
live documents that referenced it), `accept` (promote a draft, retire what it
replaces), and `status` (what is live vs retired). Document-type agnostic:
`DESIGN.md`, `SPEC-v*.md`, `RFC-*.md`, `PLAN-*.md`.

### step-back

A reassessment procedure for when an approach keeps failing. "Take a deep breath"
is read as *reconsider the framing*, not as breathing guidance. The skill
separates the **goal from the method** — restating the intended outcome without
naming the current tool — then hunts for the **assumption that makes the current
approach look necessary**, sorting verified facts from real constraints from
untested beliefs and treating previous failures as evidence rather than noise.

It then compares two or three **genuinely different** approaches (configuration
tweaks to the same method do not count), keeps the current one as the baseline,
and refuses to manufacture simplicity by quietly relaxing the user's explicit
requirements or moving work somewhere else and calling it eliminated. The output
is a short decision summary — actual goal, blocking assumption and its evidence,
better candidates, recommendation, and the cheapest reversible experiment that
could disprove it — never a questionnaire or a thought transcript.

The folder also carries an `agents/openai.yaml` manifest and an icon, so the
same skill can be dropped into Codex unchanged.

### sdlc

Anthropic's ["AI-native SDLC playbook"](https://claude.com/blog/the-ai-native-sdlc-playbook)
turned from a document into something a repo actually runs on. Six stages, each with
one named artifact and one human gate: Plan → `intent.md`, Design → `spec.md`,
Build → `plan.md` then code, Test → proof pasted into the report, Deploy → `REVIEW.md`
and the PR, Maintain → `bands.yaml` and a new `intent.md`.

The premise is that agents made writing code cheap, so the bottleneck moved to
**deciding what to build and proving it works** — and both of those get a named
artifact and a gate in front of them. Written for the solo case: one human holding
every role the guide splits across five people, and one or more agents working inside
the gates. Every gate means the same thing — the human says yes, recorded in git.

Carries the rules that are easiest to skip and most expensive to skip: state the
problem separately from the solution; never write code before `plan.md` is approved;
targets are quantifiable, never "looks good"; the agent that wrote the code does not
approve it; a mistake made twice becomes a `CLAUDE.md` entry; and the stage-6 detector
stays deterministic with no model in it.

### sdlc-jev

The screening pass that runs *before* an `sdlc` gate, so the human arrives already
knowing where to look. Each gate's criteria are prose — "covers the intent",
"concerns resolved", "targets are quantifiable" — and no regex checks prose. Asking a
chat model returns a confident paragraph you then have to re-judge yourself, which is
a second opinion rather than screening.

Instead it uses [TypeSafe](https://docs.typesafe.ai) System One (**Jev**), which
returns typed answers and calibrated probabilities rather than text. Each written
criterion becomes a question with a defined answer set; the answer comes back as a
number the policy acts on. Five gates (stages 1–5), all criteria and thresholds in
`gates.json`, nothing hardcoded in the runner. Exit codes `0` pass / `1` review /
`2` blocked, so CI can block on `2` and let `1` through with a comment.

**Stage 6 has no gate here on purpose** — the Maintain detector must stay
deterministic (sigma bands, no model). Jev belongs in the diagnose step *after* a
breach, writing the next `intent.md`.

It **never approves**: that would break the SDLC's own first and fifth principles
(human judgment above the loop; separation of duties). A clean screening means
"nothing in the written criteria tripped" — a far narrower claim than "this is good".
The shipped thresholds are starting points, not measurements; calibrate them against
an `evals/` set of artifacts whose verdict you already know, and pin a model version
so an update cannot silently move your gates. A full Design screening over two real
~5k-word documents costs about **$0.0008**.

### sbx

Wraps the [`sbx`](https://docs.docker.com/reference/cli/sbx/) CLI — Docker
Sandboxes — so untrusted or destructive work runs in a **microVM** instead of on
the host: separate kernel, own filesystem, own Docker daemon, deny-by-default
egress proxied through the host. Covers the lifecycle (`run` / `create` / `ls` /
`exec` / `stop` / `rm`), the direct-vs-`--clone` workspace choice and the
`sandbox-<name>` git remote clone mode leaves behind, network policy presets and
per-sandbox allow/deny rules, host-side secret injection (the raw key never
enters the VM), published ports, `cp`, templates, kits, and MCP.

The parts that actually bite are called out: creation-time-only flags that are
silently ignored on re-attach, `sbx policy check network <host>` before debugging
a "broken" tool inside the sandbox, direct mode not protecting the host from git
hooks and `package.json` scripts it later runs itself, and `sbx reset` being a
sign-you-out, delete-everything button.

A companion file,
[`references/test-arena.md`](../../plugins/skillz/skills/sbx/references/test-arena.md),
turns the same feature set into a **test-bench cookbook**: headless CI bootstrap,
one disposable bench per scenario, oracle (no-LLM) runs on the `shell` agent,
driving a real agent at a pty, reality-based assertions and artifact extraction,
telemetry egress via `host.docker.internal`, chaos by network denial, a nested
compose stack inside the bench's own Docker daemon, parallel matrices with a
budget guard, pre-warmed template images, per-subject kits — and an executable
credential-isolation test for the "use-but-not-read" claim. Ends with a
feature→placement map and an explicit list of what is documented versus what
still needs verifying on a signed-in host.
