---
name: croc
description: Securely transfer files, folders, or text between two computers using croc (schollz/croc) — peer-to-peer, end-to-end encrypted via a one-time code phrase, no server to run and no accounts. Use when the user wants to send/receive/beam files or text between machines that are NOT set up for SSH (different networks, someone else's computer, phone), mentions croc, or asks for a code-phrase / PAKE file transfer. For hosts that already accept passwordless SSH, prefer the file-transfer skill instead.
---

# croc

`croc` transfers files, folders, or text between **any two computers** with
**end-to-end encryption**. The two sides agree on a short **code phrase**; that
phrase drives a PAKE key exchange, and the data flows E2E-encrypted through a
relay. No port-forwarding, no accounts, no server to stand up.

## When to use this vs file-transfer

- **croc (this skill):** the two machines are not SSH-paired — different
  networks, a colleague's laptop, a phone, a fresh box. The only shared secret
  is a code phrase you read out or paste to the other side.
- **file-transfer skill:** the destination already accepts **passwordless SSH**
  (e.g. `macminim`). That path is faster and needs no code phrase. Use it when
  it applies.

## Prerequisites

- `croc` on `$PATH` on **both** machines. Check with `croc --version`.
- If missing, install (macOS): `brew install croc`. Cross-platform one-liner:
  `curl https://getcroc.schollz.com | bash`. Do **not** silently pipe-to-bash on
  the user's machine without saying so — mention the install command and let
  them run it, or run `brew install croc` if they use Homebrew.
- Nothing else. No relay to run (a public default relay is built in), no signup.

## Core usage

### Send

```bash
croc send <file-or-folder> [more files/folders ...]
croc send --text "some text or a URL"       # send text instead of a file
cat file.tar | croc send                     # send from stdin (pipe)
```

`croc send` prints a generated code phrase (e.g. `8451-crossover-almanac-tuna`)
and then **blocks**, waiting for the receiver. The code is what the other side
needs.

### Receive

The receive form is **platform-dependent** — this matters, get it right:

```bash
# Linux / macOS (default): the code MUST come from the env var, not argv
CROC_SECRET=8451-crossover-almanac-tuna croc

# Windows (default): the code as an argument is fine
croc 8451-crossover-almanac-tuna

# Any platform, interactive: run bare and croc prompts for the code
croc            # → "Enter receive code: ____"
```

**Why:** on Linux/macOS, croc's default mode **refuses** a code passed as a
command-line argument — it would leak via the process list (CVE-2023-43621). If
you run `croc <code>` there without classic mode, croc **ignores the code, prints
setup guidance, and exits 0 without receiving anything** (`src/cli/cli.go`). So
the argv form silently no-ops (and even looks like success). Use `CROC_SECRET`,
the interactive prompt, or classic mode.

`croc --classic` permanently opts a single-user machine into the plain
`croc <code>` argv form (the pre-CVE behavior). Only suggest it if the user
explicitly wants it on a machine they trust.

## Running croc from an agent (important)

`croc send` is long-running: it prints the code early, then blocks until the
receiver connects and the transfer finishes. So:

1. Start the send in the **background** (the harness's `run_in_background`), not
   as a blocking foreground call.
2. Read the emitted code phrase from its output and **relay that code to the
   user** so they can run it on the other machine.
3. Leave the process alive until the transfer completes (or the user is done),
   then let it exit. The sender quitting early aborts the transfer.

For receiving from an agent, run croc in the **foreground** — it exits on its own
when the transfer is done — and use `--yes` to skip the accept prompt. Use the
form that matches the OS, because the argv shortcut silently no-ops on Unix:

```bash
# Linux / macOS — REQUIRED form; `croc <code> --yes` here exits 0 without receiving
CROC_SECRET=<code> croc --yes

# Windows
croc <code> --yes
```

If you must drive both ends yourself: start the sender with `run_in_background`,
scrape the code from its output, then run the receiver with the OS-correct form
above.

## Security model — read before choosing a code

- **The code phrase is the entire credential.** Anyone who joins the same relay
  room with the same code and completes the PAKE gets the data. Treat it like a
  one-time password.
- **It's a race, not a broadcast.** A relay room pairs exactly **two**
  connections; once two are joined it reports "room full" and rejects a third.
  Whoever connects first wins. So a leaked/guessed code lets an attacker
  *intercept* (and your real recipient then fails with "room full") — it does
  not let a crowd all download at once.
- **Let croc generate the code.** The default random multi-word code is
  effectively unguessable within the transfer window. Only set a custom
  `--code` when you must, and never a short/predictable one.
- **The relay never sees plaintext or your full code.** The room id is a hash of
  only the first 4 characters of the code; the rest is the local PAKE secret.
  Data through the relay is E2E-encrypted (AES-256-GCM).
- **Single use.** Each code is for one transfer. Share it over a channel the
  recipient trusts.

## Useful flags

Sender (`croc send ...`):

- `--code <phrase>` / `-c` — set your own code (min 6 chars). Prefer the
  generated one.
- `--text <str>` / `-t` — send text/URLs instead of files.
- `--zip` — zip a folder before sending.
- `--exclude "node_modules,.venv"` — comma-separated substrings to skip.
- `--git` — respect `.gitignore` (skip ignored files).
- `--hash imohash` — much faster hashing for very large files (default `xxhash`).
- `--qr` / `--qrcode` — print the receive code as a QR (handy for phones).

Receiver / global:

- `--yes` — auto-accept prompts (needed for unattended/scripted receives).
- `--overwrite` — overwrite existing files without asking (pair with `--yes`).
- `--stdout` — write the received file to stdout (Unix form): `CROC_SECRET=<code> croc --yes > out`.
- `--quiet` — suppress output (scripts/automation).
- `--socks5 "127.0.0.1:9050"` — route through a SOCKS5 proxy (e.g. Tor).
- `--curve p521` — pick a different PAKE elliptic curve.

## Custom / self-hosted relay (optional)

The built-in public relay (`croc.schollz.com`) is used by default — you rarely
need this. To use your own:

```bash
croc relay                                   # run a relay (TCP 9009-9013 by default)
croc --relay "myrelay.example.com:9009" --pass YOURPASSWORD send <file>
CROC_SECRET=<code> croc --relay "myrelay.example.com:9009" --pass YOURPASSWORD   # receiver (Unix)
```

Both sides must point at the same relay and, if it's password-protected, pass
the same `--pass`.

## Notes for the assistant

- **Never paste the code into a public/external channel.** Give it to the user
  and let them deliver it to the recipient over something trusted.
- If you're driving *both* ends yourself, start the sender in the background,
  capture the code from its output, then run the receiver with the OS-correct
  form — `CROC_SECRET=<code> croc --yes` on Linux/macOS, `croc <code> --yes` on
  Windows. On Unix, the bare `croc <code>` argv form exits 0 without receiving.
- If `croc` isn't installed, stop and give the install command for the user's OS
  rather than assuming a package manager.
- Don't invent a relay or password — omit `--relay`/`--pass` unless the user
  asked for a self-hosted relay; the default public relay just works.
- A leaked code can't be "revoked" — if one is exposed before the transfer,
  cancel and start a new send (new code).
