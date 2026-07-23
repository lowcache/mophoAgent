"""phone.ingest.list — list files staged for ingest."""

import os
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from config.settings import INGEST_DIR

def _list_staged(staged_dir: Path, since: str | None, limit: int) -> list[dict]:
    if not staged_dir.exists() or not staged_dir.is_dir():
        return []
    
    files = []
    for entry in staged_dir.iterdir():
        if entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
            
        try:
            stat = entry.stat()
            size_bytes = stat.st_size
            created_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            
            if since and created_at < since:
                continue
                
            pipeline = "unknown"
            if entry.name.endswith(".json"):
                try:
                    with open(entry, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "pipeline" in data:
                            pipeline = data["pipeline"]
                except Exception:
                    pass
            
            with open(entry, "rb") as f:
                file_bytes = f.read()
            sha256_hex = hashlib.sha256(file_bytes).hexdigest()
            
            files.append({
                "name": entry.name,
                "size_bytes": size_bytes,
                "sha256": sha256_hex,
                "pipeline": pipeline,
                "created_at": created_at
            })
        except Exception:
            # Skip any single file that errors
            pass
            
    # Sort ascending by created_at
    files.sort(key=lambda x: x["created_at"])
    
    # Cap the count
    return files[:limit]

def register(mcp):
    @mcp.tool(name="phone.ingest.list")
    async def ingest_list(since: str | None = None, limit: int = 100) -> dict:
        """List files currently staged for ingest. This transfers file metadata so the
        caller can decide what to fetch (D6). Returns a dictionary with a 'files' list.
        Each file entry contains name, size_bytes, sha256, pipeline, and created_at.
        Files can be filtered by 'since' (ISO-8601 UTC string) and capped by 'limit'."""
        staged_dir = INGEST_DIR / "staged"
        return {"files": _list_staged(staged_dir, since, limit)}
