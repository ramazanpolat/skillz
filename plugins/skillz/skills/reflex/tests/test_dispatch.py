#!/usr/bin/env python3
"""Unit tests for the reflex procedures dispatcher, against a mock Jev.

No network and no key: a local HTTP server stands in for api.typesafe.ai,
answers with scripted choices, and records every request. The dispatcher runs
as a subprocess, exactly as the Claude Code hook runs it.

  python3 plugins/skillz/skills/reflex/tests/test_dispatch.py
"""
import http.server
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
DISPATCH = os.path.join(SCRIPTS, "dispatch.py")
HOOK = os.path.join(SCRIPTS, "hook.sh")


class MockJev:
    """Answers each request with the next scripted (choice, probabilities); records requests."""

    def __init__(self):
        self.requests, self.answers, self.status, self.delay = [], [], 200, 0.0
        mock = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                mock.requests.append({"body": body, "auth": self.headers.get("Authorization")})
                if mock.delay:
                    time.sleep(mock.delay)
                if mock.status != 200:
                    self.send_response(mock.status)
                    self.end_headers()
                    return
                choice, probs = mock.answers.pop(0) if mock.answers else ("none", {"none": 1.0})
                out = {"model": "jev-mock", "answers": {"p": {"type": "choice", "choice": choice,
                                                              "confidence": 1.0, "probabilities": probs}}}
                data = json.dumps(out).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1/systemone"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


OPEN_PR = """\
    ---
    name: open-pr
    title: Opening a pull request
    mode: auto
    fires_on: [bash, user_prompt]
    covers: Creating a pull request now: running gh pr create, or the user asks to open one.
    excludes: Viewing, listing or discussing existing PRs.
    ---
    1. Request `@codex review` once, in the body.
    2. Report the head only after reading it back from the remote.
    """
REPORT = """\
    ---
    name: report-pr-state
    mode: auto
    fires_on: [reply, message]
    covers: A reply that states a commit SHA or merge state without saying it was read back.
    ---
    1. Read the head back with gh pr view before stating it.
    """
PAUSED = """\
    ---
    name: remote-kill
    status: paused
    fires_on: [bash]
    covers: Killing processes by pattern over ssh.
    ---
    1. Use a bracket pattern.
    """


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jev = MockJev()

    @classmethod
    def tearDownClass(cls):
        cls.jev.close()

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="reflex-test-")
        self.pdir = os.path.join(self.tmp, "procedures")
        os.makedirs(self.pdir)
        self.jev.requests.clear()
        self.jev.answers.clear()
        self.jev.status, self.jev.delay = 200, 0.0
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("CLAUDE_", "TYPESAFE_", "REFLEX_"))}
        self.env.update(REFLEX_PROCEDURES_DIR=self.pdir, REFLEX_JEV_URL=self.jev.url,
                        TYPESAFE_API_KEY="test-key-123")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def config(self, **kw):
        cfg = {"engine": "jev"}
        cfg.update(kw)
        with open(os.path.join(self.pdir, "config.json"), "w") as f:
            json.dump(cfg, f)

    def proc(self, name, text):
        with open(os.path.join(self.pdir, f"{name}.md"), "w") as f:
            f.write(textwrap.dedent(text))

    def hook(self, event, env=None, via_sh=False):
        cmd = ["bash", HOOK] if via_sh else [sys.executable, DISPATCH, "hook"]
        r = subprocess.run(cmd, input=json.dumps(event).encode(), capture_output=True,
                           env=env or self.env, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def log(self):
        try:
            with open(os.path.join(self.pdir, "decisions.jsonl")) as f:
                return [json.loads(line) for line in f]
        except OSError:
            return []


def bash(cmd, session="s1"):
    return {"hook_event_name": "PreToolUse", "session_id": session, "prompt_id": "p1",
            "tool_name": "Bash", "tool_input": {"command": cmd}}


def stop(reply, active=False):
    # the documented Stop payload: no prompt_id
    return {"hook_event_name": "Stop", "session_id": "s1",
            "last_assistant_message": reply, "stop_hook_active": active}


def prompt(text, session="s1"):
    return {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": text}


class OptIn(Base):
    def test_no_config_is_a_no_op(self):
        self.proc("open-pr", OPEN_PR)
        self.assertIsNone(self.hook(bash("gh pr create")))
        self.assertIsNone(self.hook(bash("gh pr create"), via_sh=True))
        self.assertEqual(self.jev.requests, [])

    def test_other_engine_is_a_no_op(self):
        self.config(engine="prompt")
        self.proc("open-pr", OPEN_PR)
        self.assertIsNone(self.hook(bash("gh pr create")))
        self.assertEqual(self.jev.requests, [])

    def test_no_eligible_procedure_makes_no_call(self):
        self.config()
        self.proc("report-pr-state", REPORT)
        self.assertIsNone(self.hook(bash("gh pr create")))
        self.assertEqual(self.jev.requests, [])

    def test_paused_is_not_offered(self):
        self.config()
        self.proc("remote-kill", PAUSED)
        self.assertIsNone(self.hook(bash("ssh tr0 pkill -f x")))
        self.assertEqual(self.jev.requests, [])

    def test_no_key_and_no_ref_makes_no_call(self):
        self.config()
        self.proc("open-pr", OPEN_PR)
        env = dict(self.env)
        del env["TYPESAFE_API_KEY"]
        self.assertIsNone(self.hook(bash("gh pr create"), env=env))
        self.assertEqual(self.jev.requests, [])


class Request(Base):
    def test_request_shape(self):
        self.config(model="jev-latest")
        self.proc("open-pr", OPEN_PR)
        self.proc("report-pr-state", REPORT)
        self.proc("remote-kill", PAUSED)
        self.hook(bash("gh pr create --title x"))
        self.assertEqual(len(self.jev.requests), 1)
        req = self.jev.requests[0]
        self.assertEqual(req["auth"], "Bearer test-key-123")
        body = req["body"]
        self.assertEqual(body["model"], "jev-latest")
        self.assertEqual(body["state"]["content"], "gh pr create --title x")
        crit = body["questions"]["p"]["criteria"]
        self.assertEqual(set(crit), {"open-pr", "none"})          # only eligible, active ones
        self.assertIn("excludes", crit["open-pr"])
        self.assertEqual(body["questions"]["p"]["type"], "choice")

    def test_credentials_are_redacted(self):
        self.config()
        self.proc("open-pr", OPEN_PR)
        self.hook(bash("curl -H 'Authorization: Bearer abcdefghijkl123' --data password=hunter2 ghp_" + "a" * 30))
        sent = self.jev.requests[0]["body"]["state"]["content"]
        for secret in ("abcdefghijkl123", "hunter2", "ghp_" + "a" * 30):
            self.assertNotIn(secret, sent)
        self.assertIn("<redacted>", sent)

    def test_quoted_and_json_credentials_are_redacted(self):
        self.config()
        self.proc("open-pr", OPEN_PR)
        cmd = ("curl --data '{\"token\": \"abc123\", \"n\": 1}' "
               "&& export api_key='s3cr3t-one' && mysql password=\"two words\"")
        self.hook(bash(cmd))
        sent = self.jev.requests[-1]["body"]["state"]["content"]
        for secret in ("abc123", "s3cr3t-one", "two words"):
            self.assertNotIn(secret, sent)
        self.assertIn('"token": "<redacted>"', sent)
        self.assertIn("api_key='<redacted>'", sent)
        prev = self.log()[-1]["preview"]
        for secret in ("abc123", "s3cr3t-one", "two words"):
            self.assertNotIn(secret, prev)

    def test_event_kinds(self):
        self.config()
        self.proc("open-pr", OPEN_PR)
        self.proc("report-pr-state", REPORT)
        self.hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt": "open a PR"})
        self.hook({"hook_event_name": "PreToolUse", "session_id": "s1", "tool_name": "SendMessage",
                   "tool_input": {"to": "lead", "message": "Head is abc123"}})
        self.hook({"hook_event_name": "PreToolUse", "session_id": "s1", "tool_name": "Read",
                   "tool_input": {"file_path": "/x"}})
        kinds = [r["body"]["state"]["event"] for r in self.jev.requests]
        self.assertEqual(len(kinds), 2)                            # Read is not an event kind
        self.assertIn("user's new message", kinds[0])
        self.assertIn("message the agent is about to send", kinds[1])
        self.assertIn("to: lead", self.jev.requests[1]["body"]["state"]["content"])

    def test_long_content_is_clipped(self):
        self.config()
        self.proc("open-pr", OPEN_PR)
        self.hook(bash("x" * 20000))
        self.assertLess(len(self.jev.requests[0]["body"]["state"]["content"]), 4100)


class Decisions(Base):
    def setUp(self):
        super().setUp()
        self.config()
        self.proc("open-pr", OPEN_PR)
        self.proc("report-pr-state", REPORT)

    def test_fire_injects_the_steps(self):
        self.jev.answers.append(("open-pr", {"open-pr": 0.95, "none": 0.05}))
        out = self.hook(bash("gh pr create"))
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "PreToolUse")
        self.assertNotIn("permissionDecision", hso)
        ctx = hso["additionalContext"]
        self.assertIn("[procedure: open-pr]", ctx)
        self.assertIn("Request `@codex review` once", ctx)
        self.assertIn("Mode auto", ctx)
        self.assertIn("read-only mode", ctx)

    def test_second_fire_in_a_session_is_short(self):
        self.jev.answers += [("open-pr", {"open-pr": 0.95, "none": 0.05})] * 2
        self.hook(bash("gh pr create"))
        ctx = self.hook(bash("gh pr create"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("applies again", ctx)
        self.assertNotIn("Request `@codex review`", ctx)

    def test_new_session_gets_the_steps_again(self):
        self.jev.answers += [("open-pr", {"open-pr": 0.95, "none": 0.05})] * 2
        self.hook(bash("gh pr create", session="a"))
        ctx = self.hook(bash("gh pr create", session="b"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Request `@codex review`", ctx)

    def test_hint_band(self):
        self.jev.answers.append(("open-pr", {"open-pr": 0.6, "none": 0.4}))
        ctx = self.hook(bash("gh pr create"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("may apply", ctx)
        self.assertNotIn("Request `@codex review`", ctx)

    def test_none_and_low_confidence_say_nothing(self):
        self.jev.answers += [("none", {"open-pr": 0.1, "none": 0.9}), ("open-pr", {"open-pr": 0.4, "none": 0.35})]
        self.assertIsNone(self.hook(bash("ls")))
        self.assertIsNone(self.hook(bash("gh pr list")))

    def test_thresholds_are_configurable(self):
        self.config(fire=0.99, hint=0.9)
        self.jev.answers.append(("open-pr", {"open-pr": 0.95, "none": 0.05}))
        ctx = self.hook(bash("gh pr create"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("may apply", ctx)

    def test_decisions_are_logged(self):
        self.jev.answers.append(("open-pr", {"open-pr": 0.95, "none": 0.05}))
        self.hook(bash("gh pr create"))
        rec = self.log()[-1]
        self.assertEqual((rec["kind"], rec["choice"], rec["action"]), ("bash", "open-pr", "fire"))
        self.assertIn("ms", rec)
        self.assertEqual(rec["eligible"], ["open-pr"])

    def test_log_can_be_off(self):
        self.config(log=False)
        self.jev.answers.append(("open-pr", {"open-pr": 0.95, "none": 0.05}))
        self.hook(bash("gh pr create"))
        self.assertEqual(self.log(), [])


class Reply(Base):
    def setUp(self):
        super().setUp()
        self.config()
        self.proc("report-pr-state", REPORT)

    def test_a_matching_reply_is_blocked_once_per_turn(self):
        self.jev.answers += [("report-pr-state", {"report-pr-state": 0.97, "none": 0.03})] * 3
        out = self.hook(stop("Head is 5b5d8e9, MERGEABLE."))
        self.assertEqual(out["decision"], "block")
        self.assertIn("Read the head back", out["reason"])
        self.assertIsNone(self.hook(stop("Head is 5b5d8e9, MERGEABLE.")))    # same turn: let it stop
        # the next user message starts a new turn: the same procedure may block again
        self.hook(prompt("and the other PR?"))                                # no user_prompt procedure: no call
        out = self.hook(stop("Head is 7c1d2e3, MERGEABLE."))
        self.assertEqual(out["decision"], "block")

    def test_stop_hook_active_never_blocks(self):
        self.jev.answers.append(("report-pr-state", {"report-pr-state": 0.97, "none": 0.03}))
        self.assertIsNone(self.hook(stop("Head is 5b5d8e9.", active=True)))

    def test_a_hint_never_blocks(self):
        self.jev.answers.append(("report-pr-state", {"report-pr-state": 0.6, "none": 0.4}))
        self.assertIsNone(self.hook(stop("Head is 5b5d8e9.")))

    def test_reply_from_the_transcript(self):
        tp = os.path.join(self.tmp, "t.jsonl")
        with open(tp, "w") as f:
            f.write(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Head is abc."}]}}) + "\n")
        self.hook({"hook_event_name": "Stop", "session_id": "s1", "transcript_path": tp})
        self.assertEqual(self.jev.requests[-1]["body"]["state"]["content"], "Head is abc.")


class FailOpen(Base):
    def setUp(self):
        super().setUp()
        self.config(timeout_s=0.5)
        self.proc("open-pr", OPEN_PR)

    def test_server_error(self):
        self.jev.status = 500
        self.assertIsNone(self.hook(bash("gh pr create")))
        self.assertEqual(self.log()[-1]["action"], "error")

    def test_timeout(self):
        self.jev.delay = 2.0
        t0 = time.monotonic()
        self.assertIsNone(self.hook(bash("gh pr create")))
        self.assertLess(time.monotonic() - t0, 2.0)
        self.assertEqual(self.log()[-1]["action"], "error")

    def test_unreachable(self):
        env = dict(self.env, REFLEX_JEV_URL="http://127.0.0.1:9/v1/systemone")
        self.assertIsNone(self.hook(bash("gh pr create"), env=env))

    def test_garbage_stdin(self):
        r = subprocess.run([sys.executable, DISPATCH, "hook"], input=b"not json", capture_output=True, env=self.env)
        self.assertEqual((r.returncode, r.stdout), (0, b""))

    def test_broken_procedure_does_not_stop_the_others(self):
        with open(os.path.join(self.pdir, "broken.md"), "w") as f:
            f.write("no frontmatter here\n")
        self.jev.answers.append(("open-pr", {"open-pr": 0.95, "none": 0.05}))
        self.assertIn("[procedure: open-pr]", self.hook(bash("gh pr create"))["hookSpecificOutput"]["additionalContext"])
        r = subprocess.run([sys.executable, DISPATCH, "list"], capture_output=True, text=True, env=self.env)
        self.assertIn("BROKEN  broken.md", r.stdout)


class WithSecret(Base):
    """No key in the environment: the dispatcher re-runs under with-secret."""

    def test_key_ref_goes_through_with_secret(self):
        self.config(key_ref="file:" + os.path.join(self.tmp, "key.txt"))
        with open(os.path.join(self.tmp, "key.txt"), "w") as f:
            f.write("lent-key-456")
        fake = os.path.join(self.tmp, "bin")
        os.makedirs(fake)
        ws = os.path.join(fake, "with-secret")
        with open(ws, "w") as f:   # a stand-in: VAR=file:<path> -- cmd...
            f.write('#!/usr/bin/env bash\nspec="$1"; shift; [ "$1" = "--" ] && shift\n'
                    'var="${spec%%=*}"; ref="${spec#*=}"; export "$var"="$(cat "${ref#file:}")"\nexec "$@"\n')
        os.chmod(ws, os.stat(ws).st_mode | stat.S_IEXEC)
        env = dict(self.env, PATH=fake + os.pathsep + self.env.get("PATH", ""))
        del env["TYPESAFE_API_KEY"]
        self.proc("open-pr", OPEN_PR)
        self.jev.answers.append(("open-pr", {"open-pr": 0.95, "none": 0.05}))
        out = self.hook(bash("gh pr create"), env=env)
        self.assertEqual(self.jev.requests[-1]["auth"], "Bearer lent-key-456")
        self.assertNotIn("lent-key-456", json.dumps(out))
        self.assertIn("[procedure: open-pr]", out["hookSpecificOutput"]["additionalContext"])


class Parser(Base):
    def check(self, text, msg):
        self.proc("x", text)
        r = subprocess.run([sys.executable, DISPATCH, "list"], capture_output=True, text=True, env=self.env)
        self.assertIn(msg, r.stdout)

    def test_errors_are_named(self):
        self.check("---\nname: y\nfires_on: [bash]\ncovers: c\n---\nsteps\n", "does not match the file name")
        self.check("---\nfires_on: [bash]\n---\nsteps\n", "no `covers:`")
        self.check("---\ncovers: c\n---\nsteps\n", "no `fires_on:`")
        self.check("---\nfires_on: [shell]\ncovers: c\n---\nsteps\n", "unknown kind 'shell'")
        self.check("---\nfires_on: [bash]\ncovers: c\nmode: sometimes\n---\nsteps\n", "mode must be auto or ask")
        self.check("---\nfires_on: [bash]\ncovers: c\n---\n\n", "no steps")

    def test_list_shaped_values_break_only_their_file(self):
        self.config()
        self.proc("open-pr", OPEN_PR)
        self.proc("x", "---\nname: [x]\nfires_on: [bash]\ncovers: c\n---\nsteps\n")
        self.proc("y", "---\nfires_on: [bash]\ncovers: [a, b]\n---\nsteps\n")
        r = subprocess.run([sys.executable, DISPATCH, "list"], capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("BROKEN  x.md", r.stdout)
        self.assertIn("BROKEN  y.md", r.stdout)
        self.assertIn("open-pr", r.stdout)
        self.jev.answers.append(("open-pr", {"open-pr": 0.95, "none": 0.05}))
        self.assertIn("[procedure: open-pr]", self.hook(bash("gh pr create"))["hookSpecificOutput"]["additionalContext"])

    def test_a_good_file_lists(self):
        self.proc("open-pr", OPEN_PR)
        r = subprocess.run([sys.executable, DISPATCH, "list"], capture_output=True, text=True, env=self.env)
        self.assertIn("open-pr", r.stdout)
        self.assertIn("on=bash,user_prompt", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
