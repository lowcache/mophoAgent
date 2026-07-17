"""Shared helpers for the Phase 2 capture tools (not a tool module —
tool_registry does not import it)."""

import asyncio
import subprocess


class CaptureError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


async def run_cli(cmd: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess:
    """Run a termux-*/system CLI off the event loop."""
    def _run():
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    try:
        return await asyncio.to_thread(_run)
    except FileNotFoundError:
        raise CaptureError("CLI_NOT_FOUND", f"{cmd[0]} not installed")
    except subprocess.TimeoutExpired:
        raise CaptureError("CLI_TIMEOUT", f"{cmd[0]} exceeded {timeout:.0f}s")


def raise_for_termux_api(proc: subprocess.CompletedProcess, device: str):
    """Map common termux-api failures to error codes. PERMISSION_DENIED
    means the Termux:API companion app lacks the Android permission
    (Settings -> Apps -> Termux:API -> Permissions), not storage setup."""
    text = (proc.stdout + proc.stderr).lower()
    if "busy" in text:
        raise CaptureError(f"{device}_BUSY", f"{device.lower()} in use by another app")
    if "permission" in text or "denied" in text:
        raise CaptureError("PERMISSION_DENIED",
                           f"grant {device.lower()} permission to the Termux:API app")
    if proc.returncode != 0:
        raise CaptureError("CAPTURE_FAILED",
                           (proc.stderr or proc.stdout).strip()[:200] or "unknown failure")
