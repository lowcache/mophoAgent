"""phone.ingest.fetch — fetch a staged file and optionally mark it delivered."""

import os
import base64
import hashlib
from pathlib import Path

from config.settings import INGEST_DIR

def _fetch(staged_dir: Path, delivered_dir: Path, name: str, delete_after: bool) -> dict:
    if "/" in name or ".." in name or os.path.basename(name) != name:
        return {"error": "FILE_NOT_FOUND", "message": name}
        
    staged_file = staged_dir / name
    if not staged_file.is_file():
        return {"error": "FILE_NOT_FOUND", "message": name}
        
    try:
        with open(staged_file, "rb") as f:
            file_bytes = f.read()
            
        sha256_hex = hashlib.sha256(file_bytes).hexdigest()
        content_b64 = base64.b64encode(file_bytes).decode("utf-8")
        
        if delete_after:
            delivered_dir.mkdir(parents=True, exist_ok=True)
            delivered_file = delivered_dir / name
            os.replace(staged_file, delivered_file)
            
        return {
            "name": name,
            "sha256": sha256_hex,
            "content_b64": content_b64
        }
    except Exception:
        return {"error": "FILE_NOT_FOUND", "message": name}

def register(mcp):
    @mcp.tool(name="phone.ingest.fetch")
    async def ingest_fetch(name: str, delete_after: bool = True) -> dict:
        """Fetch the contents of a staged file. This performs the actual data transfer (D6).
        If delete_after is true, the file is moved out of the staged directory into a
        delivered directory so it is transferred exactly once.
        Returns name, sha256, and content_b64 on success.
        Errors: FILE_NOT_FOUND if the file doesn't exist or name is invalid.
        Note: The caller is responsible for HASH_MISMATCH verification."""
        staged_dir = INGEST_DIR / "staged"
        delivered_dir = INGEST_DIR / "staged-delivered"
        return _fetch(staged_dir, delivered_dir, name, delete_after)
