"""Shared helpers for the Phase 5 system tools (not a tool module —
tool_registry does not import it)."""

import asyncio
import re
import shutil
import subprocess
import time
from pathlib import Path

from config.settings import AGENT_DIR, CONFIG_DIR

# D2: the server runs under native Termux Python, so shell commands must go
# to Termux's bash, never Android's /system/bin/sh.
TERMUX_BASH = "/data/data/com.termux/files/usr/bin/bash"

BLOCKLIST_NAME = "rish_blocklist.txt"

# A successful Shizuku liveness probe is trusted this long. The guardrail
# asks for a per-call check; probing on literally every call would cost an
# extra rish exec per candidate inside free_ram's kill loop. Failures are
# never cached (see ensure_rish), so recovery is still seen immediately.
RISH_PROBE_TTL_SEC = 10.0


class SystemToolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _outcome(stdout: bytes, stderr: bytes, exit_code: int, start: float) -> dict:
    return {
        "stdout": stdout.decode(errors="replace"),
        "stderr": stderr.decode(errors="replace"),
        "exit_code": exit_code,
        "execution_time_ms": int((time.monotonic() - start) * 1000),
    }


# --- blocklist ------------------------------------------------------------

# (mtime, patterns) — reloaded when the operator edits the installed file,
# so blocklist changes take effect without bouncing the service.
_blocklist_cache: tuple[float, list[re.Pattern]] | None = None


def _blocklist_path() -> Path:
    """Installed blocklist, seeded from the repo default on first use
    (same marker-free auto-install idea as the Phase 2 share hooks)."""
    installed = CONFIG_DIR / BLOCKLIST_NAME
    if not installed.exists():
        default = AGENT_DIR / "config" / BLOCKLIST_NAME
        if default.exists():
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(default, installed)
    return installed


def load_blocklist() -> list[re.Pattern]:
    """Compiled blocklist regexes, one per non-comment line, case-sensitive
    (D10: fnmatch of a literal `rm -rf /` never matches
    `rm -rf / --no-preserve-root`; these are re.search patterns).

    Fails CLOSED — an unreadable, empty, or wholly uncompilable file raises
    BLOCKLIST_UNAVAILABLE rather than letting rish run unfiltered. The
    blocklist is a safety net against accidents, and a safety net that
    silently disappears is worse than none.
    """
    global _blocklist_cache
    path = _blocklist_path()
    try:
        mtime = path.stat().st_mtime
    except OSError as e:
        raise SystemToolError("BLOCKLIST_UNAVAILABLE",
                              f"cannot stat {path}: {e}")
    if _blocklist_cache is not None and _blocklist_cache[0] == mtime:
        return _blocklist_cache[1]
    try:
        text = path.read_text()
    except OSError as e:
        raise SystemToolError("BLOCKLIST_UNAVAILABLE",
                              f"cannot read {path}: {e}")
    patterns: list[re.Pattern] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            patterns.append(re.compile(line))
        except re.error:
            # One bad line must not void the rest of the net; a file with no
            # usable line at all still fails closed below.
            continue
    if not patterns:
        raise SystemToolError("BLOCKLIST_UNAVAILABLE",
                              f"{path} defines no usable pattern")
    _blocklist_cache = (mtime, patterns)
    return patterns


def check_blocklist(command: str) -> None:
    """Raise FORBIDDEN_COMMAND if `command` matches any blocklist pattern."""
    for pattern in load_blocklist():
        if pattern.search(command):
            raise SystemToolError(
                "FORBIDDEN_COMMAND",
                f"command matches blocklist pattern: {pattern.pattern}")


# --- termux exec ----------------------------------------------------------

async def run_shell(command: str, timeout_sec: float = 30.0,
                    workdir: str = "~") -> dict:
    """Run `command` through Termux's bash in `workdir`. Errors:
    WORKDIR_NOT_FOUND, TIMEOUT, COMMAND_NOT_FOUND (exit 127)."""
    cwd = Path(workdir).expanduser()
    if not cwd.is_dir():
        raise SystemToolError("WORKDIR_NOT_FOUND", f"{workdir} is not a directory")

    def _run():
        return subprocess.run(command, shell=True, cwd=str(cwd),
                              capture_output=True, timeout=timeout_sec,
                              executable=TERMUX_BASH)

    start = time.monotonic()
    try:
        proc = await asyncio.to_thread(_run)
    except subprocess.TimeoutExpired:
        raise SystemToolError("TIMEOUT", f"command exceeded {timeout_sec:.0f}s")
    except FileNotFoundError:
        raise SystemToolError("COMMAND_NOT_FOUND", f"{TERMUX_BASH} not found")
    if proc.returncode == 127:
        raise SystemToolError(
            "COMMAND_NOT_FOUND",
            (proc.stderr.decode(errors="replace").strip()[:200]
             or "command not found"))
    return _outcome(proc.stdout, proc.stderr, proc.returncode, start)


# --- rish / Shizuku -------------------------------------------------------

# (monotonic_at, path) of the last successful liveness probe.
_rish_probe: tuple[float, str] | None = None


async def _probe_rish(path: str, timeout_sec: float) -> bool:
    def _run():
        return subprocess.run([path, "-c", "echo rish_ok"],
                              capture_output=True, timeout=timeout_sec)
    try:
        proc = await asyncio.to_thread(_run)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return b"rish_ok" in proc.stdout


async def ensure_rish(timeout_sec: float = 5.0) -> str:
    """Path to a live rish, or raise SHIZUKU_NOT_RUNNING. rish lands on PATH
    via run.sh's $HOME/bin entry (326e88b). Successful probes are cached for
    RISH_PROBE_TTL_SEC; failures are never cached, so a Shizuku restart is
    picked up on the next call."""
    global _rish_probe
    path = shutil.which("rish")
    if not path:
        raise SystemToolError(
            "SHIZUKU_NOT_RUNNING",
            "rish is not on PATH; install it to ~/bin and start Shizuku")
    now = time.monotonic()
    if (_rish_probe is not None and _rish_probe[1] == path
            and now - _rish_probe[0] < RISH_PROBE_TTL_SEC):
        return path
    if not await _probe_rish(path, timeout_sec):
        raise SystemToolError(
            "SHIZUKU_NOT_RUNNING",
            "rish is installed but not answering; is the Shizuku service running?")
    _rish_probe = (now, path)
    return path


async def rish_call(command: str, timeout_sec: float = 10.0) -> dict:
    """Execute `command` at shell uid through Shizuku's rish (stdin mode).
    The blocklist is enforced on every path into rish, internal callers
    included — there is deliberately no bypass argument. Errors:
    FORBIDDEN_COMMAND, BLOCKLIST_UNAVAILABLE, SHIZUKU_NOT_RUNNING, TIMEOUT,
    RISH_ERROR."""
    check_blocklist(command)
    path = await ensure_rish()

    def _run():
        return subprocess.run([path], input=command.encode(),
                              capture_output=True, timeout=timeout_sec)

    start = time.monotonic()
    try:
        proc = await asyncio.to_thread(_run)
    except subprocess.TimeoutExpired:
        raise SystemToolError("TIMEOUT", f"command exceeded {timeout_sec:.0f}s")
    except OSError as e:
        raise SystemToolError("RISH_ERROR", f"rish failed to execute: {e}")
    return _outcome(proc.stdout, proc.stderr, proc.returncode, start)
