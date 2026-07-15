"""Paths and constants for the phone MCP server.

Runs under native Termux Python (D2); Path.home() is the Termux home.
"""

import json
import os
import time
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "phone-agent"
TOKEN_PATH = CONFIG_DIR / "token"
CONFIG_PATH = CONFIG_DIR / "config.json"

PORT = 8462

SERVER_START_MONOTONIC = time.monotonic()


def _bind_host() -> str:
    """Tailscale IP to bind (D1). No tailscale CLI on Android, so the IP
    comes from $PHONE_TS_IP or config.json {"tailscale_ip": "100.x.y.z"}.
    Falls back to loopback so the server is still testable before the IP
    is configured."""
    env = os.environ.get("PHONE_TS_IP")
    if env:
        return env
    if CONFIG_PATH.exists():
        try:
            ip = json.loads(CONFIG_PATH.read_text()).get("tailscale_ip")
        except (json.JSONDecodeError, OSError):
            ip = None
        if ip:
            return ip
    return "127.0.0.1"


TAILSCALE_IP = _bind_host()


def token_file_exists() -> bool:
    return TOKEN_PATH.is_file()


def get_token_from_file() -> str:
    return TOKEN_PATH.read_text().strip()
