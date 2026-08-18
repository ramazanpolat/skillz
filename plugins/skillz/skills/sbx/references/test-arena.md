# sbx as a disposable test bench

Worked, end-to-end recipes for using Docker Sandboxes as the **bench** in a test
or simulation harness: a throwaway machine that a scenario installs software
onto, drives an agent inside, and then asserts against — before being destroyed.

The running example is [gentar](https://github.com/agent-realm/gentar) (aGENT
ARena), whose vocabulary these recipes borrow: a **subject** (the component under
test) is *mounted, never baked*; a **scenario** states *decisions, not steps*; a
**bench** is disposable and *the container is the reset*; **verdicts come from
reality** (files, processes, SQL, spans, TTY) rather than from the agent's word.
Nothing here is gentar-specific — any harness with those shapes can lift it.

Read [`../SKILL.md`](../SKILL.md) first for the command surface. This file is
about *placement*: which sbx feature belongs at which point in a scenario.

## What sbx is and is not, for a harness

**It is** a per-scenario machine boundary you get for one command: separate
kernel, own filesystem, **its own Docker daemon**, deny-by-default egress
proxied through the host, and credentials that are injected into outbound
requests by that proxy instead of living in the bench.

**It is not** a compose substrate. There are no user-defined networks, no
service graph, and no way to wire two sandboxes onto a shared L2 segment. A
sandbox talks to the outside through the policy-checked proxy and to the host
through `host.docker.internal`; that is the whole topology.

So the useful split for a compose-shaped arena is:

| Layer | Vehicle |
|---|---|
| coordinator, telemetry, dashboard, nested stack-under-test | compose, as designed |
| the **bench** — the disposable pilot machine an agent works inside | a sandbox |
| the machine boundary the security and chaos tiers assert against | the sandbox boundary |

Three of gentar's design-doc objections to Docker Sandboxes are worth
re-checking against v0.38.0, because two have moved:

- *"no custom images"* — **stale.** `sbx template save` snapshots a bench, and a
  custom `Dockerfile` extending `docker/sandbox-templates:<agent>` is documented
  and supported (see [Pre-warmed benches](#pre-warmed-benches-templates)).
- *"no headless CI"* — **stale.** `sbx login --username … --password-stdin` with
  a Docker PAT, `sbx policy init <preset>` for the otherwise-interactive first-run
  prompt, and `sbx create` + `sbx exec` + `--json` give a fully non-interactive path.
- *"no custom networks"* — **still true**, and it is the real constraint. A
  multi-service stack-under-test still wants compose; run it *inside* the bench's
  own Docker daemon (see [Integration tier](#integration-tier-nested-stack-inside-the-bench)).

## Bootstrap: a CI runner, headless

Run once per runner, before any scenario. Every step here is non-interactive.

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Auth. A browser flow is not available on a runner; use a Docker PAT.
printf '%s' "$DOCKER_PAT" | sbx login --username "$DOCKER_ID" --password-stdin

# 2. Network preset. Without this, the first sandbox creation blocks on an
#    interactive prompt asking for Open / Balanced / Locked Down.
#    Values: allow-all | balanced | deny-all
sbx policy init deny-all           # arena default: nothing egresses unless a scenario allows it

# 3. Egress the arena itself needs, allowed once, globally.
sbx policy allow network "registry-1.docker.io,auth.docker.io,hub.docker.com,api.docker.com,dhi.io"

# 4. Daemon up, and a machine-readable health check.
sbx daemon start
sbx daemon status
sbx diagnose -o json > "$ARTIFACTS/sbx-diagnose.json" || true

# 5. No telemetry from the runner.
export SBX_NO_TELEMETRY=1
```

`deny-all` is the honest arena default: it makes every network dependency a
scenario declares explicit, which is exactly what a conformance suite wants to
assert. Use `balanced` if scenarios are allowed to reach package managers
without saying so.

## Bench lifecycle: the container is the reset

One sandbox per scenario, named deterministically, destroyed unconditionally.

```bash
#!/usr/bin/env bash
set -euo pipefail

SUBJECT="claude-playbooks"
SCENARIO="install-default-channel"
RUN_ID="${CI_RUN_ID:-local}"
BENCH="bench-${SUBJECT}-${SCENARIO}-${RUN_ID}"

# Destroy on every exit path, including failure and interrupt. Never repair a
# wedged bench — discard it.
cleanup() { sbx rm --force "$BENCH" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM

# The subject is mounted read-only and NOT installed; the pilot's home is a
# writable scratch dir the scenario owns.
sbx create --name "$BENCH" \
  --cpus 2 -m 4g \
  shell "$SCRATCH/home" "$PWD/subjects/$SUBJECT:ro"

# ... drive the scenario, then assert ...
```

Two facts that shape the mount layout:

- **Workspaces mount at the same absolute path they have on the host.** A
  scenario that hard-codes `/home/pilot/...` needs the host dir to be at that
  path, or must read the path from the environment instead.
- **`:ro` is per-workspace.** Mount the subject `:ro` to enforce "mounted, never
  baked, never mutated"; mount only the scratch home read-write.

For scenarios where the agent must *commit to the subject* without touching the
host checkout, use clone mode instead — the host repo is mounted read-only, the
agent works on a private in-container clone, and its commits come back over a
git remote:

```bash
sbx create --clone --name "$BENCH" claude "$PWD/subjects/$SUBJECT"
# ... agent works, commits ...
git -C "subjects/$SUBJECT" fetch "sandbox-$BENCH"
git -C "subjects/$SUBJECT" log --oneline "sandbox-$BENCH/HEAD"
sbx rm --force "$BENCH"        # also removes the sandbox-$BENCH remote
```

`--clone` is creation-time only. So are `--cpus`, `-m`, `-p`, `-t`,
`--static-mcp`, `--kit`, and `--profile`: passing them while re-attaching to an
existing sandbox is silently ignored. **A scenario that changes any of them must
create a new bench** — which is the tenet anyway.

## Oracle solution: the no-LLM smoke variant

The oracle is the reference solution that proves the scenario and its assertions
are sound without spending a token. The `shell` agent is the vehicle: no agent
binary, just a login shell.

```bash
# One-shot, non-interactive: everything after -- goes to bash.
sbx run --name "$BENCH" shell "$SCRATCH/home" -- -c "$(cat scenarios/$SCENARIO/oracle.sh)"
echo "oracle exit: $?"

# Or against an already-created bench, which is the form that composes with
# assertions and lets you keep stdout and stderr separate:
sbx exec "$BENCH" bash -lc "$(cat scenarios/$SCENARIO/oracle.sh)" \
  > "$ARTIFACTS/oracle.out" 2> "$ARTIFACTS/oracle.err"
```

Note the `-l`: `sbx exec` runs the command directly, so it does **not** read
`/etc/sandbox-persistent.sh` or any login-shell profile unless you wrap it in
`bash -lc`. A scenario whose env vars come from that file and which asserts via
a bare `sbx exec` will see a different environment than the agent did — a
classic false failure.

## Agent-in-the-loop: driving a real agent at a pty

The nightly tier drives a real agent as if a human were typing. Two transports,
both over `sbx exec`:

**Non-interactive (deterministic, preferred where the agent supports it):**

```bash
sbx exec "$BENCH" claude -p "$(render_decisions scenarios/$SCENARIO/decisions.yaml)"
```

**Interactive pty (when onboarding prompts and pickers are the thing under
test):** `sbx exec -it` allocates a pty, so `pexpect` or tmux control mode drives
it exactly as it drove an ssh session:

```python
import pexpect
child = pexpect.spawn("sbx", ["exec", "-it", BENCH, "bash", "-l"], encoding="utf-8", timeout=120)
child.expect(r"\$ ")
child.sendline("claude-playbooks install kommander")
child.expect(r"Which channel\?")     # UX assertion: the picker appeared at all
child.sendline("stable")
child.expect(r"\$ ")
transcript = child.before                # TTY output is itself a verdict source
```

`--detach-keys` matters here: the default detach sequence can be swallowed by an
agent TUI. Set an unused one (`--detach-keys 'ctrl-@,ctrl-x'`) rather than
discovering mid-run that a keystroke detached the driver instead of reaching the
agent.

`sbx run --name "$BENCH"` is the human-facing re-attach — useful when a person
takes over a failed nightly bench before it is reaped. It reads the agent from
the sandbox spec, so no agent argument is needed.

## Verdicts from reality

Every assertion class runs through `sbx exec` and yields an exit code; artifacts
come back with `sbx cp`; the bench inventory itself is machine-readable.

```bash
# Files
sbx exec "$BENCH" test -f /home/pilot/.claude-playbooks/kommander/CLAUDE.md
# Processes
sbx exec "$BENCH" bash -lc 'pgrep -f "kommander-helper" >/dev/null'
# SQL, in-bench
sbx exec "$BENCH" bash -lc 'sqlite3 /home/pilot/.local/state/app.db "select count(*) from runs" | grep -qx 1'
# Content, with the output captured for the report
sbx exec "$BENCH" cat /home/pilot/.config/app/config.toml > "$ARTIFACTS/config.toml"

# Pull whole artifact trees back to the coordinator before teardown
sbx cp "$BENCH:/home/pilot/.local/state/logs" "$ARTIFACTS/bench-logs"
sbx cp "$BENCH:/home/pilot/install.log" "$ARTIFACTS/"

# Push a fixture in the other direction
sbx cp ./fixtures/seed.db "$BENCH:/home/pilot/.local/state/app.db"

# Bench inventory as JSON: status, agent, ports, workspace
sbx ls --json > "$ARTIFACTS/benches.json"
```

`sbx cp` needs exactly one side to be `SANDBOX:PATH`; sandbox-to-sandbox is not
supported, so a scenario comparing two benches copies both out and diffs on the
coordinator.

Do the copying **before** teardown. `sbx rm` deletes everything inside the bench;
only host workspace files survive.

## Telemetry: getting spans out of a deny-all bench

The collector runs on the arena side, not in the bench. From inside a sandbox the
host is reachable as `host.docker.internal`, and that reach is policy-checked
like any other destination:

```bash
sbx policy allow network localhost:4317          # OTLP gRPC on the host collector
sbx policy check network localhost:4317          # confirm before blaming the SDK

sbx exec "$BENCH" bash -lc \
  'OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4317 run-scenario-step'
```

If a scenario's spans are missing, check policy before instrumenting anything:
`sbx policy check network <host>` answers in one call, and `sbx policy log` shows
what was actually blocked. Under `deny-all` a silent exporter is the expected
symptom of a missing rule, not a bug in the SDK.

Belt-and-braces fallback for a bench that must stay fully dark: write spans to a
file in the bench and `sbx cp` them out at teardown, then replay into the
collector from the coordinator.

## Security tier: making the isolation claim executable

This is where sbx stops being convenience and becomes the thing under test. The
"use-but-not-read" claim — the agent can *use* a credential it can never *read* —
is exactly what the host-side proxy implements, and it is directly assertable.

```bash
# Arrange: the credential lives on the host, scoped to this bench only.
gh auth token | sbx secret set github --sandbox "$BENCH"
sbx secret ls                                  # inventory for the report

# Assert 1 — the credential is NOT in the bench environment.
! sbx exec "$BENCH" bash -lc 'env | grep -Ei "GITHUB_TOKEN|GH_TOKEN|ghp_|github_pat_"'

# Assert 2 — nor anywhere in the bench filesystem the agent can read.
! sbx exec "$BENCH" bash -lc \
  'grep -rIl -E "ghp_[A-Za-z0-9]{36}|github_pat_" /home /etc /tmp 2>/dev/null | head -1 | grep .'

# Assert 3 — and yet an authenticated call still succeeds, because the proxy
#            injects the header on the way out.
sbx exec "$BENCH" bash -lc 'gh api user -q .login'
```

All three passing is the keyhouse property, proven rather than asserted in prose.
Repeat per service (`anthropic`, `openai`, a private registry) to cover each
injection path.

Adjacent leak vectors the same tier should probe, because sbx opens them
deliberately:

```bash
# SSH agent forwarding: the host agent IS forwarded into sandboxes. A bench that
# must not be able to sign or push as the pilot should prove the socket is absent.
sbx exec "$BENCH" bash -lc '[ -z "${SSH_AUTH_SOCK:-}" ] || ! ssh-add -l'

# Shared skills store: mounted read-write when sharing is on, which means a
# compromised bench can write skills that a later bench executes. Opt out for
# untrusted scenarios (documented flag; hidden from --help in v0.38.0).
sbx create --no-share-skills --name "$BENCH" shell "$SCRATCH/home"

# Egress: prove a locked-down bench really cannot reach the internet.
! sbx exec "$BENCH" bash -lc 'curl -fsS --max-time 5 https://example.com >/dev/null'
sbx policy log > "$ARTIFACTS/policy-blocked.log"
```

And the boundary itself, asserted rather than assumed: the bench's Docker daemon
is not the host's, and the host filesystem outside the mounts is not visible.

```bash
sbx exec "$BENCH" bash -lc 'docker info --format "{{.Name}}"'    # the bench's own daemon
! sbx exec "$BENCH" bash -lc 'test -e /var/run/docker.sock.host'
! sbx exec "$BENCH" bash -lc "test -d $HOME/.ssh"
```

## Chaos and reliability tier

Failures are injected at the boundary, so the subject under test needs no chaos
hooks of its own.

```bash
# Network outage, declared at creation (narrowing only — a local deny can never widen egress)
sbx create --name "$BENCH" --deny-network api.anthropic.com claude "$SCRATCH/home"

# Or mid-run, while the agent is working: cut one dependency and watch the retry path
sbx policy deny network --sandbox "$BENCH" registry.npmjs.org
sleep 30
sbx policy rm network --sandbox "$BENCH" --resource registry.npmjs.org   # heal it

# Machine sleep / resume: stop suspends, run restarts with state intact
sbx stop "$BENCH"
sbx run --name "$BENCH"

# Resource starvation, to expose OOM and timeout handling
sbx create --name "$BENCH-tiny" --cpus 1 -m 1024m shell "$SCRATCH/home"

# Evidence for the verdict
sbx policy log > "$ARTIFACTS/policy-blocked.log"
```

Because installed packages, images, config, and shell history survive
`stop`/`run` for as long as the sandbox exists, a resume scenario tests exactly
what a laptop lid-close tests. Only `sbx rm` is the reset.

## Integration tier: nested stack inside the bench

Each sandbox has **its own Docker daemon**, so a stack-under-test can be brought
up *inside* the bench with plain compose — no DinD, no sysbox, no privileged
container on the host, and the nested stack's networks are the bench's business
alone. This is the direct answer to the arena's "per-run Docker boundary" open
question.

```bash
sbx create --name "$BENCH" -p 18080:8080 shell "$SCRATCH/home" "$PWD/stacks/full:ro"

sbx exec "$BENCH" bash -lc 'cd /stacks/full && docker compose up -d --wait'
sbx exec "$BENCH" bash -lc 'docker compose -f /stacks/full/docker-compose.yml ps --format json' \
  > "$ARTIFACTS/stack-ps.json"

# The published port makes the nested stack probeable from the coordinator.
curl -fsS http://127.0.0.1:18080/healthz

sbx exec "$BENCH" bash -lc 'cd /stacks/full && docker compose logs --no-color' \
  > "$ARTIFACTS/stack.log"
```

Ports on an already-running bench, when the scenario only learns which port it
needs at runtime:

```bash
sbx ports "$BENCH" --publish 3000          # ephemeral host port
HOST_PORT=$(sbx ports "$BENCH" --json | jq -r '.[] | select(.sandboxPort==3000) | .hostPort')
curl -fsS "http://127.0.0.1:${HOST_PORT}/healthz"
sbx ports "$BENCH" --unpublish "${HOST_PORT}:3000"
```

Pulling images inside the bench needs egress: allow the registry, or the nested
`compose up` fails with a network error that looks like a broken stack.

```bash
sbx policy allow network --sandbox "$BENCH" "registry-1.docker.io,auth.docker.io,production.cloudflare.docker.com"
```

## Compatibility matrix: many benches at once

One bench per matrix cell, sized so the host survives, reaped as they finish.

```bash
#!/usr/bin/env bash
set -euo pipefail
RUN_ID="${CI_RUN_ID:-local}"
MAX_PARALLEL=4
declare -a PIDS=()

run_cell() {
  local os_tier="$1" channel="$2"
  local bench="bench-${os_tier}-${channel}-${RUN_ID}"
  trap 'sbx rm --force "$bench" >/dev/null 2>&1 || true' RETURN
  sbx create --name "$bench" --cpus 2 -m 4g -t "arena-${os_tier}:latest" \
    shell "$SCRATCH/$bench" "$PWD/subjects/claude-playbooks:ro"
  sbx exec "$bench" bash -lc "CHANNEL=$channel /subjects/claude-playbooks/install.sh"
  sbx exec "$bench" bash -lc 'claude-playbook --version'
  sbx cp "$bench:/home/pilot/install.log" "$ARTIFACTS/${bench}.log"
}

for os_tier in ubuntu24 ubuntu22; do
  for channel in stable edge; do
    run_cell "$os_tier" "$channel" &
    PIDS+=($!)
    while (( $(jobs -rp | wc -l) >= MAX_PARALLEL )); do wait -n; done
  done
done
wait "${PIDS[@]}"
```

Budget guard, in the coordinator where it belongs — sandboxes cost RAM and disk,
and a leaked one costs them until it is removed:

```bash
running=$(sbx ls --json | jq '[.[] | select(.status=="running")] | length')
(( running < 8 )) || { echo "bench budget exceeded: $running running"; exit 75; }

# Reap anything this run_id leaked, whatever the outcome
sbx ls -q | grep -- "-${RUN_ID}\$" | xargs -r -n1 sbx rm --force
```

## Pre-warmed benches: templates

Installing agents and toolchains per scenario is the slowest part of a matrix.
Do it once, snapshot, and start every bench from the snapshot.

```bash
# 1. Build the warm bench once
sbx create --name warm-builder shell "$SCRATCH/build"
sbx exec warm-builder bash -lc 'apt-get update && apt-get install -y jq sqlite3 protobuf-compiler'
sbx exec warm-builder bash -lc 'npm i -g @anthropic-ai/claude-code'

# 2. Snapshot it as a reusable image
sbx template save warm-builder arena-ubuntu24:latest
sbx rm --force warm-builder

# 3. Every scenario starts from it
sbx create --name "$BENCH" -t arena-ubuntu24:latest shell "$SCRATCH/home"

sbx template ls
sbx template rm arena-ubuntu24:latest
```

For a reproducible, version-controlled bench image, build a `Dockerfile` instead
of snapshotting — the base images are published per agent:

```dockerfile
FROM docker/sandbox-templates:claude-code
USER root
RUN apt-get update && apt-get install -y protobuf-compiler sqlite3
USER agent
```

Move it between runners as a tar, or pull it from a private registry:

```bash
sbx template save warm-builder arena-ubuntu24:v3 --output arena-ubuntu24-v3.tar
sbx template load arena-ubuntu24-v3.tar                    # on the other runner

gh auth token | sbx secret set --registry ghcr.io --password-stdin
sbx create --name "$BENCH" -t ghcr.io/agent-realm/arena-bench:v3 shell "$SCRATCH/home"
```

Two limits worth knowing before templates become the arena's caching strategy:
agent configuration files are recreated on every sandbox creation (user-level
agent settings do not survive into a template), and a template's agent must match
the agent it is started with. Never bake a secret into a template — it ships to
anyone who receives the image; use `sbx secret set` so the proxy holds it instead.

## Kits: per-subject bench extension, declaratively

A kit is the natural home for the "a subject contributes a `gentar/` directory"
contract: the subject's own repo declares what its bench needs, versioned beside
its code, and the arena passes it through with `--kit`.

`subjects/claude-playbooks/gentar/kit/spec.yaml`:

```yaml
kind: mixin

environment:
  variables:
    ARENA_SUBJECT: claude-playbooks
    OTEL_EXPORTER_OTLP_ENDPOINT: http://host.docker.internal:4317

setup:
  install:
    - command: "apt-get update && apt-get install -y jq sqlite3"
  startup:
    - command: ["/usr/local/bin/arena-span-shipper"]
      background: true
  files:
    - path: /home/pilot/.config/arena/scenario.json
      content: '{"subject": "claude-playbooks", "workdir": "${WORKDIR}"}'
      onlyIfMissing: true

permissions:
  network:
    allow:
      - registry.npmjs.org
      - "*.githubusercontent.com"
    deny:
      - telemetry.example.com

credentials:
  - service: arena-forge
    apiKey:
      name: ARENA_FORGE_TOKEN
      proxyManaged: true
      inject:
        - domain: forge.internal
          header: Authorization
          format: "Bearer %s"

agentInstructions:
  content: |
    The subject is mounted read-only at /subjects/claude-playbooks and is NOT installed.
    Install it the way a pilot would, from the instructions you are given.
```

```bash
sbx kit validate subjects/claude-playbooks/gentar/kit
sbx kit inspect  subjects/claude-playbooks/gentar/kit --json
sbx create --name "$BENCH" --kit subjects/claude-playbooks/gentar/kit \
                           --kit arena/kits/telemetry shell "$SCRATCH/home"

# Distribute a pinned kit to other runners
sbx kit pack subjects/claude-playbooks/gentar/kit -o cp-kit-1.0.zip
sbx kit push subjects/claude-playbooks/gentar/kit ghcr.io/agent-realm/cp-kit:1.0
sbx create --name "$BENCH" --kit ghcr.io/agent-realm/cp-kit:1.0 shell "$SCRATCH/home"

# Attach a mixin to a bench that is already running (chaos tier: add a deny mid-run)
sbx kit add "$BENCH" arena/kits/degraded-network
```

`credentials.apiKey.proxyManaged: true` is the declarative form of the security
tier's whole point: the key is named in the bench's environment contract but its
value is injected at the proxy, so the assertions in
[Security tier](#security-tier-making-the-isolation-claim-executable) still pass.

Kits stack (`--kit a --kit b`), `install` runs once at creation as root,
`startup` runs on every start and must be idempotent, and `HTTP_PROXY` /
`HTTPS_PROXY` are managed by sbx — a kit that overrides them breaks both policy
and credential injection. By default only `docker.io/` kit sources are allowed;
widen that deliberately with the `kit.allowedSources` setting.

## MCP-dependent scenarios

When the feature under test *is* the MCP integration, register the server once
and pin the bench's MCP set at creation:

```bash
sbx mcp add notion ...            # registration syntax varies by server type
sbx mcp ls --json
sbx create --name "$BENCH" --static-mcp notion,atlassian claude "$SCRATCH/home"
sbx mcp inspect notion
```

The set is fixed at creation — a scenario that varies MCP servers varies benches.
`sbx mcp load` pushes an already-registered server into a running sandbox, which
is the dynamic-attachment path for a scenario testing mid-session registration.

## Settings the arena should pin

```bash
sbx settings list                          # marks which settings need a daemon restart
sbx settings set kit.allowedSources ...    # if kits come from a private registry
sbx settings get clipboard.imagePaste
sbx settings unset <key>
```

Pin them in the runner bootstrap, not per scenario: they are daemon-owned and
shared by every bench on the machine.

## Teardown and the exit-code contract

```bash
sbx rm --force "$BENCH"          # one bench, no prompt
sbx rm --force --all             # everything, between suites
```

Wrap a scenario so the harness's `compose up` + exit code contract holds:

```bash
run_scenario() {
  local rc=0
  drive_scenario || rc=$?
  collect_artifacts || true       # artifacts must survive a failed scenario
  sbx rm --force "$BENCH" >/dev/null 2>&1 || true
  return "$rc"
}
```

> **Warning:** never put `sbx reset` in a suite or a cleanup path. It terminates
> every running sandbox on the machine — including other suites' benches and any
> human's work — deletes all state, policies, cached images, and stored secrets,
> and signs the runner out. It is a hand-operated recovery tool, not teardown.
> Use `sbx rm --force --all` to clear benches, and `--preserve-secrets` if a
> genuine reset is ever unavoidable.

## Feature coverage map

Every `sbx` capability and where it belongs in a scenario:

| Feature | Proper place in a scenario |
|---|---|
| `sbx login --password-stdin` | runner bootstrap, headless auth |
| `sbx policy init <preset>` | runner bootstrap — removes the interactive first-run prompt |
| `sbx daemon start/status`, `sbx diagnose -o json` | runner health gate, attached to the run report |
| `sbx create` | one disposable bench per scenario, deterministic name |
| `shell` agent | oracle solutions and any no-LLM tier |
| `claude` / `codex` / … agents | agent-in-the-loop tier |
| `sbx run --name` (re-attach) | human takeover of a failed bench before reaping |
| `-d` / `--detached` | fire-and-forget bench creation in a matrix |
| workspace `PATH` / `PATH:ro` | subject mounted read-only, scratch home read-write |
| `--clone` + `sandbox-<name>` remote | scenarios where the agent commits, host tree untouched |
| `--cpus`, `-m` | performance tier and starvation chaos |
| `-p` / `sbx ports` | probing services the subject or nested stack starts |
| `sbx exec` | every reality assertion, plus the driver transport |
| `sbx exec -it` + pexpect | UX tier: prompts, pickers, TTY-output verdicts |
| `sbx cp` | artifact and log extraction before teardown; fixture injection |
| `sbx ls --json` | bench inventory, budget guard, leak reaping |
| `sbx policy allow/deny --sandbox` | per-scenario network contract, declared not assumed |
| `--deny-network`, `sbx policy rm` | chaos tier: outage injection and healing |
| `sbx policy check` | triage before blaming the subject for a network failure |
| `sbx policy log` | evidence for a blocked-egress verdict |
| `sbx secret set [--sandbox]` | security tier: the use-but-not-read claim |
| `sbx secret set --registry` | pulling private bench images |
| bench-local Docker daemon | integration tier: nested stack, no DinD |
| `sbx template save/load`, custom Dockerfile | pre-warmed benches, matrix images, cross-runner transport |
| `sbx kit` + `spec.yaml` | the subject's contributed bench contract, versioned in its repo |
| `--static-mcp`, `sbx mcp` | scenarios whose subject *is* an MCP integration |
| `sbx skills import`, `--no-share-skills` | skill-store sharing, and the leak probe that opts out |
| `sbx settings` | runner-wide pins (kit sources, clipboard) |
| `sbx rm --force [--all]` | teardown, unconditional, on every exit path |
| `sbx reset` | never in automation — hand-operated recovery only |

## Verification status

The command and flag surface here was read from `sbx --help` on a local
**v0.38.0** install. Behavior, YAML schema, and the docs-only details
(`host.docker.internal`, SSH agent forwarding, kit fields, template limits) come
from [docs.docker.com/ai/sandboxes](https://docs.docker.com/ai/sandboxes/). The
scripts have **not** been executed end to end — the host they were written on is
not signed in to Docker. Before trusting them in a suite, confirm on a signed-in
runner that:

- `sbx exec` propagates the command's exit code (every assertion above assumes it
  does, as `docker exec` does);
- `sbx ls --json` and `sbx ports --json` field names match the `jq` paths used
  here;
- `--no-share-skills` is accepted by `create`/`run` in your version — it is
  documented but hidden from `--help` in v0.38.0.
