"""Ingest directory tree and share-hook install (Phase 2).

Single source of truth for capture/processing paths. Directories are
created synchronously at server startup (main.py __main__ block — there
is no FastMCP lifespan hook, see npu/queue.py).
"""

import shutil
from pathlib import Path

from config.settings import INGEST_DIR

INGEST_BASE = INGEST_DIR

SUBDIRS = ["audio", "images", "screenshots", "shares", "shares/spool",
           "processed/transcripts", "processed/ocr", "processed/summaries",
           "processed/scheduled", "staged", "staged-delivered",
           "queue/pending", "queue/delivering", "queue/delivered",
           "queue/failed", "errors"]

HOOKS_SRC = Path(__file__).resolve().parent.parent / "scripts" / "hooks"
HOOK_NAMES = ("termux-url-opener", "termux-file-editor")
# Any hook we installed carries this marker; a script without it is
# user-owned and must never be overwritten.
HOOK_MARKER = "phone-agent share hook"


def ensure_ingest_dirs():
    for subdir in SUBDIRS:
        (INGEST_BASE / subdir).mkdir(parents=True, exist_ok=True)


def ensure_share_hooks():
    """Install the Termux share-sheet hooks into ~/bin (Termux invokes
    ~/bin/termux-url-opener for shared URLs/text and
    ~/bin/termux-file-editor for shared files — termux-share-receive
    does not exist, D10)."""
    bin_dir = Path.home() / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name in HOOK_NAMES:
        src = HOOKS_SRC / name
        dst = bin_dir / name
        if dst.exists() and HOOK_MARKER not in dst.read_text():
            continue
        if not dst.exists() or dst.read_bytes() != src.read_bytes():
            shutil.copyfile(src, dst)
        dst.chmod(0o755)
