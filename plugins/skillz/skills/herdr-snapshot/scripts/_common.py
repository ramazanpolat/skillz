"""Shared helpers for snapshot.py and resurrect.py. Not a public CLI."""

import json
import os
import subprocess

HOME = os.path.expanduser("~")
DEFAULT_PLAYBOOKS_DIR = os.path.join(HOME, ".claude-playbooks")
DEFAULT_SNAPSHOT_DIR = os.path.join(HOME, ".herdr-snapshots")


def herdr(args, socket_path=None, timeout=20):
    env = dict(os.environ)
    if socket_path:
        env["HERDR_SOCKET_PATH"] = socket_path
    r = subprocess.run(["herdr"] + args, env=env, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"herdr {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def herdr_json(args, socket_path=None, timeout=20):
    return json.loads(herdr(args, socket_path, timeout))["result"]


def resolve_session_socket(session_name):
    """Resolve a herdr session name to its socket path via `herdr session list`."""
    out = subprocess.run(["herdr", "session", "list"], capture_output=True, text=True, timeout=10).stdout
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4 and parts[0] == session_name:
            return parts[-1]
    raise RuntimeError(f"herdr session '{session_name}' not found in `herdr session list`")


def memory_health():
    """Return (free_percent, swap_used_mb) using macOS memory_pressure / sysctl."""
    free_pct = None
    try:
        out = subprocess.run(["memory_pressure"], capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            if "free percentage" in line:
                free_pct = int(line.split(":")[1].strip().rstrip("%"))
    except Exception:
        pass
    swap_used = None
    try:
        out = subprocess.run(["sysctl", "vm.swapusage"], capture_output=True, text=True, timeout=10).stdout
        for tok in out.split():
            if tok.startswith("used"):
                pass
        # format: "vm.swapusage: total = 0.00M  used = 0.00M  free = 0.00M  (encrypted)"
        import re
        m = re.search(r"used\s*=\s*([\d.]+)M", out)
        if m:
            swap_used = float(m.group(1))
    except Exception:
        pass
    return free_pct, swap_used


def running_resume_sessions():
    """Set of session ids currently running as `claude --resume <id>` anywhere on the host."""
    import re
    out = subprocess.run(["ps", "-Ao", "args"], capture_output=True, text=True, timeout=10).stdout
    ids = set()
    for line in out.splitlines():
        m = re.search(r"claude\s+--resume\s+([0-9a-f-]{36})", line)
        if m:
            ids.add(m.group(1))
    return ids


def pid_is_claude(pid):
    """True if `pid` is alive AND is actually a claude process.

    A bare `kill -0 <pid>` is not enough after a reboot: PIDs restart from low
    numbers, so an old lock's recorded pid can coincidentally belong to an
    unrelated process (a macOS reboot handed pid 472 to WiFiAgent once, not
    Claude Code) and read as falsely "still running". Checking the command name
    too is what catches that.
    """
    if not pid:
        return False
    try:
        out = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, timeout=5).stdout
        return "/claude" in out or out.strip() == "claude"
    except Exception:
        return False
