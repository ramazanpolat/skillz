---
name: sbx
description: "Run an AI coding agent — or a plain shell — inside an isolated Docker Sandbox microVM with its own kernel, filesystem, Docker daemon, and deny-by-default network, using the `sbx` CLI. Use whenever the user wants to run something risky, untrusted, or destructive away from the host: try a random install script, let an agent work unsupervised, build/test an unknown repo, reproduce a bug in a clean box, or run a second agent in parallel. Also use for anything naming sbx or Docker Sandboxes — sandbox lifecycle, workspace and --clone mode, network policy, secrets, ports, file copy, MCP, templates, and kits. Also use when building a test or simulation harness on sandboxes — disposable per-scenario benches, headless CI runs, parallel matrices, chaos via network denial, and executable credential-isolation tests. Not for the sprite skills (sprites.dev VMs), nor for plain `docker run` containers."
---

# sbx — Docker Sandboxes

`sbx` runs an agent inside a **microVM**: separate kernel, own filesystem, own
Docker daemon, own network stack. The agent can `rm -rf`, install anything,
build images, and run untrusted code without touching the host. Only what you
explicitly mount and what network policy explicitly allows crosses the boundary.

The CLI is free, including commercial use. Only org-wide governance is paid.

For scripted, disposable **test benches** — scenario harnesses, CI matrices,
chaos and credential-isolation suites — read
[`references/test-arena.md`](references/test-arena.md): full worked scripts for
every feature below, placed where they belong in a scenario.

## Reach for this when

- Something must run but should not run **on the host**: unknown install script,
  untrusted repo, dependency with a suspicious postinstall, a build that wants root.
- An agent should work **unsupervised**. Inside a sandbox, approval prompts stop
  being the safety mechanism — isolation is.
- You need **a clean box** to reproduce a bug, or **several boxes at once** for
  parallel agents on the same repo.

Not this skill: `sprite` / `test-on-sprite` (sprites.dev VMs, different product),
plain `docker run` (shares host kernel and daemon — not an isolation boundary
for a hostile workload).

## Preflight

```bash
sbx version          # installed? (this doc written against v0.38.0)
sbx ls               # signed in? errors with "Not authenticated to Docker" if not
```

- Not installed — macOS: `brew trust docker/tap && brew install docker/tap/sbx`;
  Windows: `winget install -h Docker.sbx`; Linux (Ubuntu 24.04+, KVM):
  `curl -fsSL https://get.docker.com | sudo SBX=1 sh`.
  Requirements: macOS 14+ Apple silicon / Windows 11 with Hypervisor Platform /
  Ubuntu 24.04+ with KVM and the user in the `kvm` group.
- Not signed in — `sbx login` is **interactive** (browser). Don't run it blind
  from a tool call: tell the user to run `sbx login` themselves, e.g. by typing
  `! sbx login`. For CI and headless runners, authenticate with a Docker PAT:
  `printf '%s' "$DOCKER_PAT" | sbx login --username "$DOCKER_ID" --password-stdin`,
  then `sbx policy init balanced` so the first sandbox doesn't block on the
  interactive network-preset prompt.
- Daemon trouble — `sbx daemon status`, `sbx daemon restart`, then `sbx diagnose`.

## Core loop

```bash
sbx run claude                       # create (if needed) + attach, cwd as workspace
sbx run --name my-box claude .       # named, explicit workspace
sbx create --name my-box claude .    # create in background, don't attach
sbx run --name my-box                # re-attach later, from any directory
sbx run -d --name my-box claude      # create, print sandbox ID, exit (detached)
sbx ls                               # status, agent, ports, workspace  (--json, -q)
sbx exec -it my-box bash             # shell inside
sbx stop my-box                      # suspend, keep state
sbx rm my-box                        # delete sandbox and everything in it
```

Agents: `claude`, `codex`, `copilot`, `cursor`, `docker-agent`, `droid`,
`gemini`, `kiro`, `opencode`, `shell`. `shell` is the agent-less sandbox (a bash
login shell, no agent binary) — the right pick for "just run this untrusted thing
somewhere safe" and for scripted one-shots.

Pass agent arguments after `--`:

```bash
sbx run claude -- --continue                  # resume a session
sbx run claude -- -p "summarize this repo"    # non-interactive prompt
sbx run shell -- -c 'make test'               # one-shot command, exits when done
```

For `shell`, args after `--` that start with a flag are appended to `bash -l`;
bare words replace `-l` entirely.

Default name is `<agent>-<workdir>`. `sbx exec` starts a stopped sandbox first,
and its flags mirror `docker exec` (`-i`, `-t`, `-d`, `-u`, `-w`, `-e`,
`--env-file`, `--privileged`).

While a sandbox exists, installed packages, Docker images, config changes, and
shell history survive `stop`/`run`. `rm` destroys all of it — host workspace
files and the shared skills store survive.

## Workspace: direct vs clone

**Direct (default)** — the workspace is bind-mounted read-write. The agent's
edits are live on the host, same as if it ran locally.

```bash
sbx run claude ~/project-a ~/shared-libs:ro ~/docs:ro   # extra mounts, :ro = read-only
```

Workspaces mount **at the same absolute path they have on the host**, so paths in
scripts and configs keep working. A middle option between direct and clone is a
host git worktree — isolated branch, still live on the host:

```bash
git worktree add -b feat/x ../x-work && sbx run claude ../x-work
```

**Clone (`--clone`)** — the host repo is mounted read-only and the agent works on
a private in-container git clone. Host working tree is never touched; the
agent's commits come back through a `sandbox-<name>` git remote added to the
host repo (removed when the sandbox is removed).

```bash
sbx create --clone --name my-box claude .
git fetch sandbox-my-box && git log sandbox-my-box/HEAD   # on the host, afterwards
```

`--clone` must be set **at creation time**; it is a no-op when re-attaching.

**Choose clone whenever the point is to keep the host tree clean** — unsupervised
agents, untrusted repos, experiments you may want to throw away.

Direct mode caveat worth stating to the user: the sandbox does not protect the
host from files that the **host** later executes implicitly — git hooks, CI
config, IDE tasks, `package.json` scripts, build files. Git hooks don't show in
`git diff`; check `.git/hooks` separately before running anything the agent
touched.

## Resources and ports

```bash
sbx run --cpus 4 -m 8g claude              # default: all host CPUs, 50% RAM (max 32 GiB)
sbx run -p 8080:3000 --name my-box claude  # publish at creation
sbx ports my-box                           # list  (--json)
sbx ports my-box --publish 3000            # ephemeral host port for sandbox 3000
sbx ports my-box --publish 8080:3000
sbx ports my-box --unpublish 8080:3000
```

Spec: `[[HOST_IP:]HOST_PORT:]SANDBOX_PORT[/PROTOCOL]`. Without HOST_IP it binds
loopback only. Protocols: `tcp`, `tcp4`, `tcp6`, `udp`, `udp4`, `udp6`.
`-p` on `run` applies only at creation — use `sbx ports` on an existing sandbox.

## Moving files

```bash
sbx cp ./config.json my-box:/home/user/     # host  -> sandbox
sbx cp my-box:/home/user/out.log ./         # sandbox -> host
sbx cp ./src/ my-box:/home/user/src         # directory
```

One side must be `SANDBOX:PATH`; sandbox-to-sandbox is not supported.

## Network policy

Egress is **deny-by-default and proxied through the host**. Direct UDP and ICMP
are blocked. Presets, chosen on first start or after `sbx policy reset`:

| Preset | `policy init` value | Behavior |
|---|---|---|
| Open | `allow-all` | all outbound traffic allowed |
| Balanced | `balanced` | deny by default, allowlist for model APIs, package managers, code hosts, registries, cloud services |
| Locked Down | `deny-all` | everything blocked, model provider APIs included |

Balanced is the sane default. In CI or headless, set it before any other command
(the interactive prompt has nothing to prompt):

```bash
sbx policy init balanced
```

```bash
sbx policy ls                                     # active rules (--wide, --include-inactive,
                                                  #  --source local|org|kit, --decision allow|deny)
sbx policy allow network registry.npmjs.org
sbx policy allow network "api.example.com,*.npmjs.org,*.pypi.org"
sbx policy allow network --sandbox my-box internal.corp
sbx policy deny network --sandbox my-box telemetry.example.com
sbx policy check network api.example.com          # would this be allowed?
sbx policy rm network --resource api.example.com  # or --id <rule-id>
sbx policy log                                    # what got blocked
sbx policy inspect
sbx policy reset                                  # back to preset choice (--force)
```

Resources take domains, wildcards, and CIDR ranges. Deny at creation time,
narrowing only:

```bash
sbx run --deny-network telemetry.example.com claude
```

Under org governance only **org** allow rules grant access; local allow rules go
inactive (visible via `--include-inactive`), while local deny rules still apply.

Services on the **host** are reachable as `host.docker.internal`, and that reach
is policy-checked like anything else — allow it explicitly:

```bash
sbx policy allow network localhost:11434
sbx exec my-box curl -fsS http://host.docker.internal:11434/api/tags
```

**When an agent inside a sandbox fails to reach something, check policy before
debugging the tool.** `sbx policy check network <host>` answers it in one call,
and `sbx policy log` shows what was actually blocked.

## Secrets

```bash
sbx secret ls
sbx secret set github -t "$(gh auth token)"        # service secret
sbx secret import                                  # adopt secrets from host env vars
sbx secret rm <name>
sbx secret set --registry ghcr.io --password-stdin # registry secret (host-only by default)
```

Service secrets (`github`, `anthropic`, `openai`, …) are held on the host; the
host-side proxy injects the auth header into outbound requests, so **the raw
value never enters the VM**. Registry secrets are for pulling private template
and kit images — they stay host-only unless `--all-sandboxes` / `--sandbox` is set.

Claude Code with a subscription: run `/login` inside the sandbox. The session
token stays on the host.

Never paste a raw key into a sandbox shell or a file in the workspace — that
defeats the proxy injection and puts the credential inside the VM.

Per-launch injection without storing anything, e.g. from 1Password:

```bash
ANTHROPIC_API_KEY="op://Work/Anthropic/credential" op run -- sbx run claude
```

The host **SSH agent is forwarded into sandboxes**, so an agent inside can sign
commits with the host key (`git config --global gpg.format ssh`). That is a
convenience and an exposure — for an untrusted workload, check `SSH_AUTH_SOCK`
inside the sandbox and decide deliberately.

## Templates — pre-warmed sandboxes

Snapshot a sandbox once, start every later one from it:

```bash
sbx create --name builder shell .
sbx exec builder bash -lc 'apt-get update && apt-get install -y jq sqlite3'
sbx template save builder my-bench:v1          # snapshot -> reusable image
sbx rm --force builder
sbx run -t my-bench:v1 shell .                 # start from it
sbx template ls | rm my-bench:v1
```

Version-controlled alternative — a Dockerfile on the published base image:

```dockerfile
FROM docker/sandbox-templates:claude-code
USER root
RUN apt-get update && apt-get install -y protobuf-compiler
USER agent
```

Move it between machines, or pull from a private registry:

```bash
sbx template save builder my-bench:v1 --output my-bench-v1.tar
sbx template load my-bench-v1.tar
gh auth token | sbx secret set --registry ghcr.io --password-stdin
sbx run -t ghcr.io/myorg/my-bench:v1 claude
```

The template's agent must match the agent it is started with, agent config files
are recreated on every creation (user settings don't survive into a template),
and a secret baked into a template ships to everyone who gets the image — use
`sbx secret set` instead.

## Kits — declarative sandbox extension

A kit is a versioned YAML spec (plus optional files) that adds env vars, install
and startup commands, files, network rules, and proxy-managed credentials.
Perfect for "this project's sandbox needs X", checked in beside the code.

`my-kit/spec.yaml`:

```yaml
kind: mixin
environment:
  variables:
    MY_TOOL_HOME: /home/agent/.my-tool
setup:
  install:
    - command: "apt-get update && apt-get install -y jq"
  startup:
    - command: ["my-daemon"]
      background: true
  files:
    - path: /home/agent/.my-tool/config.json
      content: '{"workspace": "${WORKDIR}"}'
      onlyIfMissing: true
permissions:
  network:
    allow: ["api.example.com", "*.cdn.example.com"]
    deny:  ["telemetry.example.com"]
credentials:
  - service: my-service
    apiKey:
      name: MY_SERVICE_API_KEY
      proxyManaged: true
      inject:
        - domain: api.example.com
          header: Authorization
          format: "Bearer %s"
agentInstructions:
  content: |
    jq is installed. Config lives at ~/.my-tool/config.json.
```

```bash
sbx kit validate ./my-kit
sbx kit inspect ./my-kit --json
sbx run claude --kit ./my-kit --kit ./another-kit        # kits stack
sbx kit add my-box ./my-kit                              # mixin into a running sandbox
sbx kit pack ./my-kit -o my-kit-1.0.zip
sbx kit push ./my-kit ghcr.io/myorg/my-kit:1.0
sbx run claude --kit ghcr.io/myorg/my-kit:1.0
sbx run claude --kit "git+https://github.com/docker/sbx-kits-contrib.git#ref=v0.1.0&dir=code-server"
```

`install` runs once at creation as root; `startup` runs on every start and must
be idempotent. Never override `HTTP_PROXY` / `HTTPS_PROXY` from a kit — sbx owns
them, and policy plus credential injection ride on them. Only `docker.io/` kit
sources are allowed by default (`kit.allowedSources` setting widens it).

## MCP, skills, settings

```bash
sbx mcp add <name> ... ; sbx mcp ls ; sbx mcp inspect <name> ; sbx mcp auth <name>
sbx run --static-mcp notion,atlassian claude    # fixed MCP set, creation-time only
sbx mcp load <name> my-box                      # push a registered server into a running sandbox

sbx skills import --dry-run                     # (experimental) share host agent skills
sbx skills import --force
sbx create --no-share-skills claude .           # opt out (documented; hidden from --help in v0.38.0)

sbx settings list | get <key> | set <key> <value> | unset <key>
sbx setup            # (experimental) detect host config, import env secrets
sbx setup ssh        # SSH config, for VS Code / Cursor attach over SSH
sbx tui              # interactive dashboard
```

The skills store is mounted **read-write**, so a sandbox can write skills a later
sandbox executes — `--no-share-skills` for anything untrusted.

`~/.claude` and other user-level agent config stay on the host; project-level
config is visible inside. Env vars nothing else covers go in
`/etc/sandbox-persistent.sh` inside the sandbox — read only by shells started
**after** the edit, and bypassed by `sbx exec` unless wrapped in `bash -lc`.

## Gotchas

- Creation-time-only flags: `--clone`, `--static-mcp`, `-p/--publish`, `--profile`,
  `-t/--template`, `--cpus`, `-m`. Re-attaching with them silently ignores them —
  to change any of these, `sbx rm` and recreate.
- `sbx rm` prompts; scripts need `-f`. `--all` removes every sandbox.
- Sub-subcommand `--help` (e.g. `sbx policy allow --help`) prints root help
  instead — read `sbx policy --help` and the online reference.
- Deep `sbx` calls fail with `ERROR: Not authenticated to Docker` before doing
  anything. Check `sbx ls` first rather than misreading it as a real failure.
- `sbx logout` stops **all** running sandboxes.
- `sbx exec CMD` does not run a login shell: no `/etc/sandbox-persistent.sh`, no
  profile. Wrap it — `sbx exec my-box bash -lc '...'` — or the environment
  differs from the one the agent saw.
- `sbx exec -it` allocates a pty; if a TUI eats the detach sequence, set an
  unused one with `--detach-keys`.
- Telemetry opt-out: `SBX_NO_TELEMETRY=1`.

> **Warning:** `sbx reset` is destructive and irreversible — it terminates every
> running sandbox (losing in-flight agent work), deletes all sandbox state,
> policies, cached images, and stored secrets, and signs you out. Confirm with the
> user first, and prefer `sbx rm <name>` for one sandbox. `--preserve-secrets`
> keeps secrets; `-f` skips the prompt.

## Docs

- Overview: https://docs.docker.com/ai/sandboxes/
- CLI reference: https://docs.docker.com/reference/cli/sbx/
- Install: https://docs.docker.com/ai/sandboxes/install/
- Security model: https://docs.docker.com/ai/sandboxes/security/
- Local policy: https://docs.docker.com/ai/sandboxes/security/policy/
- Workflow patterns: https://docs.docker.com/ai/sandboxes/workflows/
- Kits: https://docs.docker.com/ai/sandboxes/customize/kits/
- Templates: https://docs.docker.com/ai/sandboxes/customize/templates/
- FAQ: https://docs.docker.com/ai/sandboxes/faq/
- Test-bench recipes (this skill): [`references/test-arena.md`](references/test-arena.md)
