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

# Backend inference servers (D4: persistent processes, loopback only).
LLM_PORT = 8463      # llama-server: classify + llm (qwen2.5-1.5b-q4)
EMBED_PORT = 8464    # llama-server --embedding (all-minilm-l6-v2-q4)
WHISPER_PORT = 8465  # whisper-server (whisper-small.en-q4_0)

MODELS_DIR = Path.home() / "phone-agent" / "models"
INGEST_DIR = Path.home() / "ingest"

# Private root for backend binaries and their shared libs, populated from
# extracted Termux .debs (llama-cpp) and the whisper.cpp source build.
# Kept out of $PREFIX so the dpkg database stays truthful; `pkg install
# llama-cpp python-{numpy,pillow,onnxruntime}` supersedes it.
RUNTIME_DIR = Path.home() / "phone-agent-runtime"

# whisper.cpp windows audio internally, so this is a sanity cap against
# runaway batch jobs, not the 30s model context.
AUDIO_MAX_SEC = 600

# Lazy-loaded backends are stopped after this much idle time.
LAZY_UNLOAD_IDLE_SEC = 30

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
