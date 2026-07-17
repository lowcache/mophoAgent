"""File naming and writing for captured artifacts."""

import hashlib
import os
import time
from pathlib import Path

from ingest.layout import INGEST_BASE


def generate_filename(subdir: str, kind: str, extension: str) -> Path:
    """Unique path YYYYMMDD_HHMMSS_{kind}_{hash5}.{ext} under a subdir,
    e.g. generate_filename("audio", "raw", "wav")."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    raw = f"{timestamp}_{os.urandom(4).hex()}"
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:5]
    return INGEST_BASE / subdir / f"{timestamp}_{kind}_{short_hash}.{extension}"


def write_capture(subdir: str, kind: str, extension: str, data: bytes) -> Path:
    """Write raw bytes to the ingest directory and return the path."""
    path = generate_filename(subdir, kind, extension)
    path.write_bytes(data)
    return path
