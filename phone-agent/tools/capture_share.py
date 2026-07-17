import asyncio
import json
import time
from pathlib import Path

from config.settings import INGEST_DIR

SPOOL_DIR = INGEST_DIR / "shares" / "spool"
SHARES_DIR = INGEST_DIR / "shares"
ERRORS_DIR = INGEST_DIR / "errors"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"}


def register(mcp):
    @mcp.tool(name="phone.capture.share")
    async def capture_share(timeout_sec: int = 30) -> dict:
        """Receive content shared to Termux via the Android share sheet
        (spooled by the ~/bin/termux-url-opener and termux-file-editor
        hooks — termux-share-receive does not exist, D10). Oldest queued
        share first; source_app is not observable from the hooks and is
        always null. Errors: TIMEOUT, SHARE_NOT_SUPPORTED."""
        deadline = time.monotonic() + timeout_sec
        while True:
            for entry in sorted(SPOOL_DIR.glob("*.json")):
                try:
                    data = json.loads(entry.read_text())
                except (json.JSONDecodeError, OSError):
                    entry.rename(ERRORS_DIR / entry.name)
                    continue
                entry.rename(SHARES_DIR / entry.name)
                content = str(data.get("content", ""))
                kind = data.get("type", "text")
                if kind == "text" and content.lower().startswith(("http://", "https://")):
                    kind = "url"
                elif kind == "file" and Path(content).suffix.lower() in IMAGE_EXTS:
                    kind = "image"
                if kind not in ("text", "url", "image", "file"):
                    return {"error": "SHARE_NOT_SUPPORTED",
                            "message": f"unsupported share type {kind!r}"}
                return {"type": kind, "content": content, "source_app": None}
            if time.monotonic() >= deadline:
                return {"error": "TIMEOUT",
                        "message": f"no share received within {timeout_sec}s"}
            await asyncio.sleep(0.5)
