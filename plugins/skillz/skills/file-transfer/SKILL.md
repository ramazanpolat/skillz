---
name: file-transfer
description: Transfer files to or from the macminim Mac mini (or any passwordless-SSH host) using rsync over SSH. Use when the user wants to send, copy, upload, push, download, pull, or sync files/folders to/from macminim or another SSH host alias.
---

# file-transfer

Push and pull files between this machine and a remote host that already accepts
**passwordless SSH** (key-based auth). The default host is `macminim`.

The skill wraps `scripts/transfer.sh`, which uses `rsync -avz` over SSH so
transfers are resumable, recursive, and skip unchanged files.

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
