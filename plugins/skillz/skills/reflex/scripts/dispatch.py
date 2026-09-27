#!/usr/bin/env python3
"""reflex procedures: Jev decides when a standing procedure applies, and which.

A procedure is a file in <config>/procedures/<name>.md: a trigger (covers,
excludes, the event kinds it may fire on) and the steps to follow. Nothing of
it sits in the prompt. On every eligible event, a Claude Code hook sends the
event and the eligible triggers to TypeSafe's Jev, which returns one choice
with calibrated probabilities; a confident match injects the procedure's
steps at that moment.

Usage:
  dispatch.py hook                     a Claude Code hook event on stdin
                                       (UserPromptSubmit, PreToolUse, Stop)
  dispatch.py test <kind> <content>    dry run: print the decision; nothing
                                       is injected, logged or remembered
  dispatch.py eval <events.json>       [[kind, content, expected], ...]:
                                       accuracy and latency
  dispatch.py list                     procedures: status, mode, kinds, fires
  dispatch.py log [N]                  the last N decisions (default 20)
  dispatch.py check                    config, procedures, key, one live call

Kinds: user_prompt, bash, write, edit, message, reply.

Standard library only. In hook mode it fails open: any error, a missing key
or a slow answer means no output and exit 0, so work never waits on Jev.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

VERSION = "0.9.0"
DEFAULTS = {
    "engine": "jev",
    "model": "jev-latest",
    "fire": 0.8,        # at or above: inject the steps (or block a reply)
    "hint": 0.5,        # at or above, below fire: a one-line hint
    "timeout_s": 2.5,   # the Jev call; the hook itself has a longer budget
    "key_ref": None,    # e.g. "keychain:typesafe", resolved through with-secret
    "log": True,        # decisions.jsonl in the procedures dir
    "api_url": "https://api.typesafe.ai/v1/systemone",
}
KINDS = ("user_prompt", "bash", "write", "edit", "message", "reply")
KIND_LABEL = {
    "user_prompt": "the user's new message to the agent",
    "bash": "a shell command the agent is about to run",
    "write": "a file the agent is about to write",
    "edit": "an edit the agent is about to make to a file",
    "message": "a message the agent is about to send to another agent or session",
    "reply": "the agent's final reply to the user, about to be shown",
}
INSTRUCTIONS = (
    "An AI coding agent is at the moment described by `event` and `content`. "
    "Which standing procedure applies to this moment, if any? Pick none unless "
    "the procedure's condition clearly holds for this very moment."
)
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_CONTENT = 4000


class ProcedureError(ValueError):
    pass


# ---- where things live --------------------------------------------------------

def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def procedures_dir():
    return os.environ.get("REFLEX_PROCEDURES_DIR") or os.path.join(config_dir(), "procedures")


def load_config(pdir):
    path = os.path.join(pdir, "config.json")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict):
        raise ValueError("config.json is not an object")
    out = dict(DEFAULTS)
    out.update(cfg)
    if os.environ.get("REFLEX_JEV_URL"):          # tests point this at a mock
        out["api_url"] = os.environ["REFLEX_JEV_URL"]
    return out


# ---- procedure files ------------------------------------------------------------

def parse_procedure(path):
    """A procedure file: '---' frontmatter of `key: value` lines, then the steps."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("---\n"):
        raise ProcedureError("no frontmatter (the file must start with ---)")
    end = text.find("\n---", 4)
    if end < 0:
        raise ProcedureError("frontmatter is not closed with ---")
    meta = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ProcedureError(f"not a `key: value` line: {line!r}")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        meta[key.strip()] = value
    for key in ("name", "title", "mode", "status", "covers", "excludes"):
        if key in meta and not isinstance(meta[key], str):
            raise ProcedureError(f"`{key}:` must be a single value, not a list")
    body = text[end + 4:].lstrip("\n").rstrip() + "\n"
    stem = os.path.splitext(os.path.basename(path))[0]
    name = meta.get("name", stem)
    if not NAME_RE.match(name) or name == "none":
        raise ProcedureError(f"bad name {name!r}: lowercase-with-dashes, and not 'none'")
    if name != stem:
        raise ProcedureError(f"name {name!r} does not match the file name {stem}.md")
    if not meta.get("covers"):
        raise ProcedureError("no `covers:` (the condition Jev matches)")
    kinds = meta.get("fires_on")
    if isinstance(kinds, str):
        kinds = [kinds]
    if not kinds:
        raise ProcedureError("no `fires_on:` (the event kinds it may fire on)")
    for k in kinds:
        if k not in KINDS:
            raise ProcedureError(f"unknown kind {k!r} in fires_on (one of {', '.join(KINDS)})")
    mode = meta.get("mode", "ask")
    if mode not in ("auto", "ask"):
        raise ProcedureError(f"mode must be auto or ask, not {mode!r}")
    status = meta.get("status", "active")
    if status not in ("active", "paused"):
        raise ProcedureError(f"status must be active or paused, not {status!r}")
    if not body.strip():
        raise ProcedureError("no steps after the frontmatter")
    return {"name": name, "title": meta.get("title", ""), "mode": mode, "status": status,
            "fires_on": kinds, "covers": meta["covers"], "excludes": meta.get("excludes", ""),
            "body": body, "path": path}


def load_procedures(pdir):
    """(procedures, errors): every <name>.md in the dir; a bad file is reported, not fatal."""
    procs, errors = [], []
    for fn in sorted(os.listdir(pdir)):
        if not fn.endswith(".md") or fn.startswith((".", "_")) or fn.upper() == "README.MD":
            continue
        try:
            procs.append(parse_procedure(os.path.join(pdir, fn)))
        except (OSError, ProcedureError, UnicodeDecodeError) as e:
            errors.append(f"{fn}: {e}")
        except Exception as e:  # noqa: BLE001 -- one bad file must never hide the others
            errors.append(f"{fn}: {type(e).__name__}: {e}")
    return procs, errors


def eligible(procs, kind):
    return [p for p in procs if p["status"] == "active" and kind in p["fires_on"]]


# ---- the event ------------------------------------------------------------------

def clip(text, limit=MAX_CONTENT):
    text = text or ""
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n[...]\n" + text[-half:]


BEARER = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}")
_KEY = r"(password|passwd|pwd|token|secret|api[_-]?key|authorization)"
# key, then = or : (a JSON key's closing quote allowed), then a value that is
# quoted ('...' or "...", spaces included), or bare. A bare value after `:`
# (YAML, a header) runs to the end of the line; after `=` (shell) to the next
# space. Bare values never start with a JSON bracket, and stop at , } ] ;
KEYED = re.compile(r"(?i)\b" + _KEY + r"([\"']?\s*([=:])\s*)"
                   r"(?:(\"|')(.*?)\4|(?![{\[])([^\s'\"{}\[\],;][^'\"{}\[\],;\n]*|[^\s'\"{}\[\],;]+))")
FLAG = re.compile(r"(?i)(--(?:password|passwd|token|secret|api-key|apikey|auth-token)(?:=|\s+))(?:(\"|')(.*?)\2|[^\s'\"]+)")
USERINFO = re.compile(r"(\b[a-z][a-z0-9+.-]*://[^/\s:@]+):[^@\s/]+@", re.I)
TOKENS = re.compile(r"\b(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})\b")


def _keyed(m):
    key, sep, op = m.group(1), m.group(2), m.group(3)
    if m.group(4):                                  # quoted: keep the quotes
        return f"{key}{sep}{m.group(4)}<redacted>{m.group(4)}"
    value = m.group(6)
    if op == "=":                                   # shell style: the value ends at a space
        rest = value.split(None, 1)
        return f"{key}{sep}<redacted>" + (value[len(rest[0]):] if rest else "")
    return f"{key}{sep}<redacted>"                  # YAML / header: to the end of the line


def _flag(m):
    q = m.group(2) or ""
    return f"{m.group(1)}{q}<redacted>{q}"


def redact(text):
    """Best effort: values that look like credentials never leave the machine."""
    text = BEARER.sub(r"\1 <redacted>", text)
    text = USERINFO.sub(r"\1:<redacted>@", text)
    text = FLAG.sub(_flag, text)
    text = KEYED.sub(_keyed, text)
    return TOKENS.sub("<redacted>", text)


def last_reply_from_transcript(path):
    """Fallback for older Claude Code without last_assistant_message on Stop."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 262144))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except (OSError, TypeError):
        return ""
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        msg = d.get("message") if isinstance(d, dict) else None
        if d.get("type") == "assistant" and isinstance(msg, dict):
            parts = msg.get("content")
            if isinstance(parts, list):
                text = "\n".join(p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text")
                if text.strip():
                    return text
    return ""


def event_from_hook(d):
    """(kind, content) for a hook event, or (None, None) when nothing applies."""
    ev = d.get("hook_event_name")
    if ev == "UserPromptSubmit":
        return "user_prompt", d.get("prompt") or ""
    if ev == "Stop":
        return "reply", d.get("last_assistant_message") or last_reply_from_transcript(d.get("transcript_path"))
    if ev == "PreToolUse":
        tool = d.get("tool_name") or ""
        ti = d.get("tool_input") or {}
        if tool == "Bash":
            return "bash", ti.get("command") or ""
        if tool == "Write":
            return "write", f"file: {ti.get('file_path', '')}\n{ti.get('content', '')}"
        if tool in ("Edit", "MultiEdit", "NotebookEdit"):
            new = ti.get("new_string") or ti.get("new_source") or json.dumps(ti.get("edits") or "")
            return "edit", f"file: {ti.get('file_path') or ti.get('notebook_path', '')}\n{new}"
        if tool == "SendMessage":
            return "message", f"to: {ti.get('to', '')}\n{ti.get('message', '')}"
    return None, None


def kind_label(kind):
    return KIND_LABEL[kind]


# ---- Jev ------------------------------------------------------------------------

def api_key(cfg):
    return os.environ.get("TYPESAFE_API_KEY") or None


def rerun_with_secret(cfg, argv, stdin_bytes, timeout=None):
    """No key in the environment but a key_ref: run again with with-secret lending it.

    The value never passes through this process's argv or output; with-secret
    resolves the reference and hands it to the child as TYPESAFE_API_KEY.
    Returns (ran, stdout_bytes, exit_code)."""
    ref = cfg.get("key_ref")
    if not ref or os.environ.get("REFLEX_UNDER_WITH_SECRET") or not shutil.which("with-secret"):
        return False, b"", 0
    if not re.match(r"^[A-Za-z0-9_-]+:[A-Za-z0-9_./#@:-]+$", str(ref)):
        return False, b"", 0
    env = dict(os.environ, REFLEX_UNDER_WITH_SECRET="1")
    try:
        r = subprocess.run(["with-secret", f"TYPESAFE_API_KEY={ref}", "--", sys.executable, os.path.abspath(__file__), *argv],
                           input=stdin_bytes, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return True, b"", 1
    except (OSError, subprocess.SubprocessError):
        return True, b"", 1
    return True, r.stdout, r.returncode


def criteria_for(procs):
    crit = {}
    for p in procs:
        c = {"covers": p["covers"]}
        if p["excludes"]:
            c["excludes"] = p["excludes"]
        crit[p["name"]] = c
    crit["none"] = "None of the above applies to this event."
    return crit


def ask_jev(cfg, key, kind, content, procs):
    """(choice, probabilities, latency_ms) from one Choice question."""
    body = {"model": cfg["model"],
            "state": {"event": kind_label(kind), "content": content},
            "questions": {"p": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": criteria_for(procs)}}}
    req = urllib.request.Request(cfg["api_url"], data=json.dumps(body).encode("utf-8"),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                          "User-Agent": f"skillz-reflex/{VERSION}"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=float(cfg["timeout_s"])) as r:
        resp = json.load(r)
    ms = int((time.monotonic() - t0) * 1000)
    ans = resp["answers"]["p"]
    return ans["choice"], ans.get("probabilities") or {ans["choice"]: 1.0}, ms


def decide(cfg, choice, probs):
    p = float(probs.get(choice, 0.0))
    if choice == "none" or p < float(cfg["hint"]):
        return "none", p
    return ("fire" if p >= float(cfg["fire"]) else "hint"), p


# ---- per-session memory -------------------------------------------------------------

def state_path(pdir, session):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session or "no-session")[:120]
    return os.path.join(pdir, ".state", f"{safe}.json")


def load_state(pdir, session):
    try:
        with open(state_path(pdir, session), encoding="utf-8") as f:
            st = json.load(f)
        if not isinstance(st, dict):
            raise ValueError("state is not an object")
    except (OSError, ValueError):
        st = {}
    if not isinstance(st.get("fired"), dict):
        st["fired"] = {}
    if not isinstance(st.get("reply_blocks"), list):
        st["reply_blocks"] = []
    return st


def save_state(pdir, session, st):
    path = state_path(pdir, session)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"            # per writer: concurrent hooks never share one
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f)
    os.replace(tmp, path)
    # opportunistic cleanup: state older than 7 days, and temp files older than 1 hour
    try:
        now = time.time()
        for fn in os.listdir(os.path.dirname(path)):
            fp = os.path.join(os.path.dirname(path), fn)
            age = now - os.path.getmtime(fp)
            if age > 7 * 86400 or (fn.endswith(".tmp") and age > 3600):
                os.remove(fp)
    except OSError:
        pass


def log_decision(cfg, pdir, rec):
    if not cfg.get("log", True):
        return
    try:
        with open(os.path.join(pdir, "decisions.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ---- what the agent sees ------------------------------------------------------------

def mode_rule(mode):
    if mode == "auto":
        return "Mode auto: follow the steps, then report."
    return "Mode ask: state the match and the steps you propose, then wait for the user's go before doing any of them."


def fire_text(proc, kind, p, first):
    if not first:
        return (f"[procedure: {proc['name']}] applies again to this {kind_label(kind)} (p={p:.2f}, Jev): "
                f"the same steps as earlier in this session ({proc['path']}).")
    title = f"{proc['title']}\n" if proc["title"] else ""
    return (f"[procedure: {proc['name']}] Jev matched this moment ({kind_label(kind)}; p={p:.2f}). "
            f"{mode_rule(proc['mode'])}\n"
            f"Disclose it at the top of your reply: \"[procedure: {proc['name']}] firing: <one-line reason>\". "
            f"If the user asked for read-only mode, do nothing and say it would have fired.\n"
            f"{title}--- steps ({proc['path']}) ---\n{proc['body']}")


def hint_text(proc, kind, p):
    return (f"[procedure: {proc['name']}] may apply to this {kind_label(kind)} (p={p:.2f}, Jev). "
            f"It covers: {proc['covers']} If that holds right now, read {proc['path']} and follow it; otherwise ignore this.")


def reply_block_text(proc, p):
    return (f"[procedure: {proc['name']}] applies to the reply you were about to give (p={p:.2f}, Jev). "
            f"Before finishing, follow it, then give the corrected reply. {mode_rule(proc['mode'])}\n"
            f"--- steps ({proc['path']}) ---\n{proc['body']}")


# ---- modes --------------------------------------------------------------------------

def run_hook(argv):
    raw = sys.stdin.buffer.read()
    pdir = procedures_dir()
    try:
        cfg = load_config(pdir)
    except (OSError, ValueError):
        return 0                                       # not opted in, or unreadable: stay out of the way
    if cfg.get("engine") != "jev":
        return 0
    try:
        d = json.loads(raw.decode("utf-8") or "{}")
    except ValueError:
        return 0
    kind, content = event_from_hook(d)
    if not kind:
        return 0
    session = d.get("session_id") or ""
    if kind == "user_prompt":
        # a new turn: a reply blocked in the last turn may be blocked again
        st = load_state(pdir, session)
        if st.get("reply_blocks"):
            st["reply_blocks"] = []
            save_state(pdir, session, st)
    procs, _ = load_procedures(pdir)
    cands = eligible(procs, kind)
    if not cands:
        return 0                                       # nothing can fire on this kind: no call
    key = api_key(cfg)
    if not key:
        ran, out, _ = rerun_with_secret(cfg, argv, raw, timeout=float(cfg["timeout_s"]) + 4)
        if ran:
            sys.stdout.buffer.write(out)
        return 0                                       # a hook always exits 0
    content = redact(clip(content))
    rec = {"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "session": session,
           "kind": kind, "eligible": [p["name"] for p in cands],
           "sha": hashlib.sha256(content.encode("utf-8")).hexdigest()[:16], "preview": content[:120]}
    try:
        choice, probs, ms = ask_jev(cfg, key, kind, content, cands)
    except (urllib.error.URLError, OSError, ValueError, KeyError, TimeoutError) as e:
        rec.update(action="error", error=type(e).__name__ + ": " + str(e)[:200])
        log_decision(cfg, pdir, rec)
        return 0
    action, p = decide(cfg, choice, probs)
    rec.update(choice=choice, p=round(p, 4), ms=ms, action=action)
    proc = next((x for x in cands if x["name"] == choice), None)
    out = None
    if proc and action != "none":
        st = load_state(pdir, session)
        if kind == "reply":
            # at most once per turn: reply_blocks is emptied by the next user message
            if action == "fire" and not d.get("stop_hook_active") and proc["name"] not in st["reply_blocks"]:
                st["reply_blocks"] = st["reply_blocks"] + [proc["name"]]
                out = {"decision": "block", "reason": reply_block_text(proc, p)}
                rec["action"] = "block"
            else:
                rec["action"] = "none"                 # never block a reply twice for the same turn
        elif action == "fire":
            first = st["fired"].get(proc["name"], 0) == 0
            st["fired"][proc["name"]] = st["fired"].get(proc["name"], 0) + 1
            out = {"hookSpecificOutput": {"hookEventName": d.get("hook_event_name"),
                                          "additionalContext": fire_text(proc, kind, p, first)}}
        else:
            out = {"hookSpecificOutput": {"hookEventName": d.get("hook_event_name"),
                                          "additionalContext": hint_text(proc, kind, p)}}
        save_state(pdir, session, st)
    log_decision(cfg, pdir, rec)
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


def need_key(cfg, argv):
    """Key for the CLI modes, or None after re-running this mode under with-secret
    (its output already printed; the process then exits with the child's code)."""
    key = api_key(cfg)
    if key:
        return key
    ran, out, code = rerun_with_secret(cfg, argv, b"")      # the CLI waits as long as it takes
    if ran:
        sys.stdout.buffer.write(out)
        sys.stdout.flush()
        if code and not out:
            sys.exit(f"the run under with-secret failed (exit {code}): check `with-secret --check TYPESAFE_API_KEY={cfg.get('key_ref')}`")
        sys.exit(code)
    sys.exit("No key: set TYPESAFE_API_KEY, or put a key_ref in config.json and install with-secret.")


def run_test(argv):
    if len(argv) < 3:
        sys.exit("usage: dispatch.py test <kind> <content>")
    kind, content = argv[1], argv[2]
    if kind not in KINDS:
        sys.exit(f"unknown kind {kind!r}: one of {', '.join(KINDS)}")
    pdir = procedures_dir()
    cfg = load_config(pdir)
    key = need_key(cfg, argv)          # first: a re-run under with-secret prints everything once
    procs, errors = load_procedures(pdir)
    for e in errors:
        print(f"skipped {e}")
    cands = eligible(procs, kind)
    print(f"eligible for {kind}: {', '.join(p['name'] for p in cands) or '(none: no call)'}")
    if not cands:
        return 0
    choice, probs, ms = ask_jev(cfg, key, kind, redact(clip(content)), cands)
    action, p = decide(cfg, choice, probs)
    top = sorted(probs.items(), key=lambda kv: -kv[1])[:3]
    print(f"choice: {choice} (p={p:.2f}), {ms} ms -> {action}")
    print("top: " + ", ".join(f"{k} {v:.2f}" for k, v in top))
    return 0


def run_eval(argv):
    if len(argv) < 2:
        sys.exit("usage: dispatch.py eval <events.json>")
    with open(argv[1], encoding="utf-8") as f:
        events = json.load(f)
    pdir = procedures_dir()
    cfg = load_config(pdir)
    procs, errors = load_procedures(pdir)
    if not [p for p in procs if p["status"] == "active"]:
        sys.exit(f"no active procedures in {pdir}: nothing to evaluate")
    key = need_key(cfg, argv)
    for e in errors:
        print(f"skipped {e}")
    ok, lat, rows = 0, [], []
    for kind, content, want in events:
        cands = eligible(procs, kind)
        if not cands:
            got, p, ms = "none", 1.0, 0
        else:
            choice, probs, ms = ask_jev(cfg, key, kind, redact(clip(content)), cands)
            action, p = decide(cfg, choice, probs)
            got = choice if action == "fire" else "none"
            lat.append(ms)
        hit = got == want
        ok += hit
        rows.append(f"{'ok ' if hit else 'XX '} {got:18} p={p:.2f} {ms:5d}ms want={want:18} | {kind}: {content[:60]!r}")
    print("\n".join(rows))
    lat.sort()
    med = lat[len(lat) // 2] if lat else 0
    print(f"\n{ok}/{len(events)} as expected (fire threshold {cfg['fire']}); Jev calls {len(lat)}, median {med} ms")
    return 0 if ok == len(events) else 1


def fire_counts(pdir):
    counts = {}
    try:
        with open(os.path.join(pdir, "decisions.jsonl"), encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("action") in ("fire", "block"):
                    counts[r.get("choice")] = counts.get(r.get("choice"), 0) + 1
    except OSError:
        pass
    return counts


def run_list(argv):
    pdir = procedures_dir()
    procs, errors = load_procedures(pdir)
    counts = fire_counts(pdir)
    for p in procs:
        print(f"{p['name']:24} {p['status']:6} {p['mode']:4} fires={counts.get(p['name'], 0):<4} on={','.join(p['fires_on'])}  {p['title']}")
    for e in errors:
        print(f"BROKEN  {e}")
    if not procs and not errors:
        print("no procedures")
    return 0


def run_log(argv):
    n = int(argv[1]) if len(argv) > 1 else 20
    path = os.path.join(procedures_dir(), "decisions.jsonl")
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()[-n:]
    except OSError:
        print("no decisions logged yet")
        return 0
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        p = r.get("p")
        print(f"{r.get('ts', '')} {r.get('kind', ''):11} {r.get('action', ''):5} "
              f"{r.get('choice', '-'):18} {'' if p is None else f'p={p:.2f}':7} {r.get('error', '') or r.get('preview', '')[:60]!r}")
    return 0


def run_check(argv):
    pdir = procedures_dir()
    try:
        cfg = load_config(pdir)
    except (OSError, ValueError) as e:
        print(f"procedures dir: {pdir}")
        print(f"config.json: MISSING or bad ({e}); the hook stays a no-op")
        return 1
    if not api_key(cfg) and cfg.get("key_ref") and not os.environ.get("REFLEX_UNDER_WITH_SECRET"):
        need_key(cfg, argv)            # re-runs this check with the key lent, then exits
    print(f"procedures dir: {pdir}")
    print(f"config: engine={cfg['engine']} model={cfg['model']} fire={cfg['fire']} hint={cfg['hint']} "
          f"timeout_s={cfg['timeout_s']} key_ref={cfg.get('key_ref') or '-'}")
    procs, errors = load_procedures(pdir)
    print(f"procedures: {len(procs)} ok, {len(errors)} broken")
    for e in errors:
        print(f"  BROKEN {e}")
    key = need_key(cfg, argv)
    active = [p for p in procs if p["status"] == "active"]
    if not active:
        print("live call: skipped (no active procedures)")
        return 0
    try:
        choice, probs, ms = ask_jev(cfg, key, "bash", "ls -la", active)
    except Exception as e:  # noqa: BLE001 -- report whatever went wrong
        print(f"live call: FAILED ({type(e).__name__}: {e})")
        return 1
    print(f"live call: ok, {ms} ms (a harmless `ls -la` -> {choice}, p={probs.get(choice, 0):.2f})")
    return 0


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 2
    mode = argv[0]
    if mode == "hook":
        try:
            return run_hook(argv)
        except Exception:  # noqa: BLE001 -- a hook must never break the session
            return 0
    handlers = {"test": run_test, "eval": run_eval, "list": run_list, "log": run_log, "check": run_check}
    if mode not in handlers:
        print(__doc__.strip())
        return 2
    return handlers[mode](argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
