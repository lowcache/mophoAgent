import json
import os
import secrets
import logging
import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()

def generate_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"

@dataclass
class QueueItem:
    id: str
    type: str
    created_at: str
    priority: int
    payload: dict
    status: str
    retry_count: int = 0
    max_retries: int = 5
    resolved_locally: bool = False
    deduplicated: bool = False

class QueueManager:
    """
    Durable priority queue backed by JSON files moved between status directories.
    Handles enqueue, dequeue, acknowledge, fail, and list operations.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.pending_dir = self.base_dir / "queue" / "pending"
        self.delivering_dir = self.base_dir / "queue" / "delivering"
        self.delivered_dir = self.base_dir / "queue" / "delivered"
        self.failed_dir = self.base_dir / "queue" / "failed"

        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.delivering_dir.mkdir(parents=True, exist_ok=True)
        self.delivered_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, d: Path, item_id: str) -> Path:
        return d / f"{item_id}.json"

    def _write_atomic(self, path: Path, item: QueueItem) -> None:
        tmp = path.parent / (path.name + ".tmp")
        with open(tmp, "w") as f:
            json.dump(asdict(item), f)
        os.replace(tmp, path)

    async def enqueue(self, item: QueueItem) -> None:
        item.status = "pending"
        path = self._path(self.pending_dir, item.id)
        await asyncio.to_thread(self._write_atomic, path, item)

    async def dequeue(self, item_id: str) -> QueueItem:
        src = self._path(self.pending_dir, item_id)
        if not src.exists():
            raise FileNotFoundError(f"Item {item_id} not found in pending queue.")

        dst = self._path(self.delivering_dir, item_id)
        await asyncio.to_thread(src.rename, dst)

        def _read_and_update() -> QueueItem:
            with open(dst, "r") as f:
                data = json.load(f)
            it = QueueItem(**data)
            it.status = "delivering"
            self._write_atomic(dst, it)
            return it

        return await asyncio.to_thread(_read_and_update)

    async def acknowledge(self, item_id: str) -> None:
        src = self._path(self.delivering_dir, item_id)
        dst = self._path(self.delivered_dir, item_id)
        await asyncio.to_thread(src.rename, dst)

        def _read_and_update() -> None:
            with open(dst, "r") as f:
                data = json.load(f)
            it = QueueItem(**data)
            it.status = "delivered"
            self._write_atomic(dst, it)

        await asyncio.to_thread(_read_and_update)

    async def fail(self, item_id: str) -> None:
        def _process_fail() -> None:
            src = self._path(self.delivering_dir, item_id)
            with open(src, "r") as f:
                data = json.load(f)
            it = QueueItem(**data)
            it.retry_count += 1

            if it.retry_count >= it.max_retries:
                it.status = "failed"
                dst = self._path(self.failed_dir, item_id)
            else:
                it.status = "pending"
                dst = self._path(self.pending_dir, item_id)
            # Persist the incremented retry_count + new status BEFORE the move,
            # so a crash mid-fail never loses the increment (retries would
            # otherwise loop forever).
            self._write_atomic(src, it)
            src.rename(dst)

        await asyncio.to_thread(_process_fail)

    async def requeue_failed(self, item_id: str) -> None:
        """Move a failed item back to pending with retry_count reset to 0
        (a deliberate manual retry). Raises FileNotFoundError if absent."""
        def _do() -> None:
            src = self._path(self.failed_dir, item_id)
            with open(src, "r") as f:
                data = json.load(f)
            it = QueueItem(**data)
            it.status = "pending"
            it.retry_count = 0
            dst = self._path(self.pending_dir, item_id)
            self._write_atomic(src, it)
            src.rename(dst)
        await asyncio.to_thread(_do)

    async def discard_failed(self, item_id: str) -> None:
        """Permanently delete a failed item. Raises FileNotFoundError if absent."""
        await asyncio.to_thread(self._path(self.failed_dir, item_id).unlink)

    def list_items(self, status_dir: Path, types: list[str] | None = None, limit: int = 50) -> list[QueueItem]:
        items = []
        for p in status_dir.glob("*.json"):
            try:
                with open(p, "r") as f:
                    data = json.load(f)
                item = QueueItem(**data)
                if types is None or item.type in types:
                    items.append(item)
            except Exception as e:
                logger.error("Failed to read %s: %s", p, e)

        items.sort(key=lambda x: (x.priority, x.created_at))
        return items[:limit]

    def list_pending(self, types: list[str] | None = None, limit: int = 50) -> list[QueueItem]:
        return self.list_items(self.pending_dir, types, limit)

    def counts(self) -> dict:
        return {
            "pending": len(list(self.pending_dir.glob("*.json"))),
            "delivering": len(list(self.delivering_dir.glob("*.json"))),
            "delivered": len(list(self.delivered_dir.glob("*.json"))),
            "failed": len(list(self.failed_dir.glob("*.json")))
        }
