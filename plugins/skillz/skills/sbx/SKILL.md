---
name: sbx
description: "Run an AI coding agent — or a plain shell — inside an isolated Docker Sandbox microVM with its own kernel, filesystem, Docker daemon, and deny-by-default network, using the `sbx` CLI. Use whenever the user wants to run something risky, untrusted, or destructive away from the host: try a random install script, let an agent work unsupervised, build/test an unknown repo, reproduce a bug in a clean box, or run a second agent in parallel. Also use for anything naming sbx or Docker Sandboxes — sandbox lifecycle (run, create, ls, exec, stop, rm), workspace and --clone mode, network policy (allow/deny/presets), secrets, published ports, file copy, MCP servers, templates, and kits. Not for the sprite skills (sprites.dev VMs) and not for plain `docker run` containers, which share the host kernel and daemon."
---

# sbx — Docker Sandboxes

`sbx` runs an agent inside a **microVM**: separate kernel, own filesystem, own
Docker daemon, own network stack. The agent can `rm -rf`, install anything,
build images, and run untrusted code without touching the host. Only what you
explicitly mount and what network policy explicitly allows crosses the boundary.

The CLI is free, including commercial use. Only org-wide governance is paid.

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
  `! sbx login`. Non-interactive form is `sbx login --username <u> --password-stdin`.
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
`gemini`, `kiro`, `opencode`, `shell`. `shell` is the agent-less sandbox — the
right pick for "just run this untrusted thing somewhere safe".

Pass agent arguments after `--`:

```bash
sbx run claude -- --continue
```

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

**When an agent inside a sandbox fails to reach something, check policy before
debugging the tool.** `sbx policy check network <host>` answers it in one call.

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

## Extras

```bash
sbx mcp ls | add | inspect | load | auth | rm      # MCP servers, brokered by a host-side gateway
sbx run --static-mcp notion,atlassian claude       # fixed MCP set, creation-time only
sbx template save | ls | rm | load                 # snapshot a sandbox as a reusable image
sbx run -t <tag> claude                            # start from that template
sbx kit add | pack | push | pull | inspect | validate   # (experimental) declarative YAML extensions
sbx run --kit ./my-kit claude
sbx skills import                                  # (experimental) share host agent skills into sandboxes
sbx setup                                          # (experimental) detect host config, import env secrets
sbx setup ssh                                      # SSH config, for VS Code / Cursor attach
sbx settings list | get | set | unset              # daemon-owned persistent settings
sbx tui                                            # interactive dashboard
```

`~/.claude` and other user-level agent config stay on the host; project-level
config is visible inside. Use `sbx skills import` to share skills.
Per-sandbox env vars that nothing else covers go in `/etc/sandbox-persistent.sh`
inside the sandbox — read only by shells started **after** the edit, and bypassed
by `sbx exec` unless wrapped in `bash -c`.

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
- FAQ: https://docs.docker.com/ai/sandboxes/faq/
