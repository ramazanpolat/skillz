---
name: file-transfer
description: Move files to or from a passwordless-SSH host (e.g. the macminim Mac mini) using rsync over SSH. Every trigger requires an SSH host — use it when the user names an SSH alias such as macminim, or clearly means one, and then wants to push to it, pull/download/fetch FROM it, list a directory on it, or run an unattended or scripted sync against it (rsync needs nobody at the far end and skips unchanged files). Do NOT use it when the other end is a service rather than an SSH host — a URL, a git remote, a package registry, an artifact store, or a cloud bucket is other tools' work, whether uploading or downloading. For a general "send this to someone" request, a phone, or any machine that is not SSH-paired, use the croc skill instead.
---

# file-transfer

Push and pull files between this machine and a remote host that already accepts
**passwordless SSH** (key-based auth). The default host is `macminim`.

The skill wraps `scripts/transfer.sh`, which uses `rsync -avz` over SSH so
transfers are resumable, recursive, and skip unchanged files.

## When to use this vs croc

**`croc` is the default for general "send this to someone" requests.** This skill
is the specialist, and it has one precondition: **a named passwordless-SSH host**
(e.g. `macminim`). It only speaks rsync-over-ssh, so without such a host it does
not apply at all. Given one, pick it for what croc cannot do:

- the transfer completes **unattended** — croc needs a person at the far end to
  type a code phrase, with both ends live at once;
- you are **pulling** from that host, or **listing** a directory on it — croc is
  push-only;
- you want a repeatable or **scripted sync** that skips unchanged files.

Otherwise — a colleague's laptop, a phone, any machine not SSH-paired — use the
`croc` skill. And when the other end is a **service** rather than a person or an
SSH host — a URL, a git remote, a package registry, an artifact store, a cloud
bucket — it is neither skill's job, uploading or downloading alike.

## Prerequisites

- `ssh <host>` must connect without a password (verify with
  `ssh -o BatchMode=yes macminim true`).
- `rsync` present on both ends (standard on macOS).

## Usage

Run the bundled script. From the skill directory:

```bash
# local -> remote (push)
./scripts/transfer.sh push <local-path> [remote-dest]

# remote -> local (pull)
./scripts/transfer.sh pull <remote-path> [local-dest]

# list a remote directory
./scripts/transfer.sh ls [remote-path]
```

Defaults: push lands in the remote home (`~/`); pull lands in the current dir (`.`).

### Options

- `-H, --host <alias>` — target a different SSH host (default `macminim`, or `$SKILLZ_HOST`).
- `-n, --dry-run` — preview the transfer without moving anything.
- `-h, --help` — full help.

### Examples

```bash
./scripts/transfer.sh push ./report.pdf                  # -> macminim:~/report.pdf
./scripts/transfer.sh push ./build/ ~/deploys/app/       # copy dir CONTENTS (trailing slash)
./scripts/transfer.sh push ./build  ~/deploys/           # copy the build DIR itself
./scripts/transfer.sh pull ~/logs/app.log ./logs/        # macminim -> ./logs/
./scripts/transfer.sh -H macmini2 push ./data.csv        # different host
./scripts/transfer.sh -n push ./big-dir/ ~/dest/         # dry run first
```

## Notes for the assistant

- A **trailing slash** on a source directory copies its *contents*; no trailing
  slash copies the *directory itself*. Mirror what the user asked for.
- Prefer a `--dry-run` first for large or destructive-looking transfers, then
  confirm before the real run.
- Remote paths may use `~` and globs; they expand on the remote shell.
- If `ssh <host>` fails (wrong alias, no key), stop and tell the user — do not
  prompt for or type a password.
- To target a host other than `macminim`, pass `-H <alias>` or set
  `SKILLZ_HOST`. The alias must already exist in the user's SSH config.
