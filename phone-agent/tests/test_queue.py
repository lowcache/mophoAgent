import sys
import asyncio
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from msgqueue.manager import QueueManager, QueueItem, generate_id, timestamp

def test_enqueue_dequeue():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = QueueManager(Path(tmpdir))
        item = QueueItem(id=generate_id("tst"), type="t", created_at=timestamp(), priority=1, payload={}, status="")
        asyncio.run(queue.enqueue(item))

        assert queue.counts()["pending"] == 1
        assert queue.list_pending()[0].id == item.id

        dequeued = asyncio.run(queue.dequeue(item.id))
        assert dequeued.id == item.id
        assert dequeued.status == "delivering"
        assert queue.counts()["pending"] == 0
        assert queue.counts()["delivering"] == 1

def test_acknowledge():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = QueueManager(Path(tmpdir))
        item = QueueItem(id=generate_id("tst"), type="t", created_at=timestamp(), priority=1, payload={}, status="")
        asyncio.run(queue.enqueue(item))
        asyncio.run(queue.dequeue(item.id))
        asyncio.run(queue.acknowledge(item.id))

        assert queue.counts()["delivering"] == 0
        assert queue.counts()["delivered"] == 1

def test_fail_increment_and_persist():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = QueueManager(Path(tmpdir))
        item = QueueItem(id=generate_id("tst"), type="t", created_at=timestamp(), priority=1, payload={}, status="")
        asyncio.run(queue.enqueue(item))
        asyncio.run(queue.dequeue(item.id))

        asyncio.run(queue.fail(item.id))

        assert queue.counts()["delivering"] == 0
        assert queue.counts()["pending"] == 1

        path = queue._path(queue.pending_dir, item.id)
        with open(path) as f:
            data = json.load(f)
        assert data["retry_count"] == 1
        assert data["status"] == "pending"

def test_fail_max_retries():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = QueueManager(Path(tmpdir))
        item = QueueItem(id=generate_id("tst"), type="t", created_at=timestamp(), priority=1, payload={}, status="", max_retries=1)
        asyncio.run(queue.enqueue(item))
        asyncio.run(queue.dequeue(item.id))

        asyncio.run(queue.fail(item.id))

        assert queue.counts()["failed"] == 1

        path = queue._path(queue.failed_dir, item.id)
        with open(path) as f:
            data = json.load(f)
        assert data["retry_count"] == 1
        assert data["status"] == "failed"

def test_list_pending_sort():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = QueueManager(Path(tmpdir))
        item1 = QueueItem(id=generate_id("p2"), type="t", created_at=timestamp(), priority=2, payload={}, status="")
        item2 = QueueItem(id=generate_id("p0"), type="t", created_at=timestamp(), priority=0, payload={}, status="")

        asyncio.run(queue.enqueue(item1))
        asyncio.run(queue.enqueue(item2))

        items = queue.list_pending()
        assert len(items) == 2
        assert items[0].id == item2.id
        assert items[1].id == item1.id

def test_list_pending_type_filter():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = QueueManager(Path(tmpdir))
        item1 = QueueItem(id=generate_id("t1"), type="typeA", created_at=timestamp(), priority=1, payload={}, status="")
        item2 = QueueItem(id=generate_id("t2"), type="typeB", created_at=timestamp(), priority=1, payload={}, status="")

        asyncio.run(queue.enqueue(item1))
        asyncio.run(queue.enqueue(item2))

        filtered = queue.list_pending(types=["typeB"])
        assert len(filtered) == 1
        assert filtered[0].id == item2.id

def test_requeue_failed_resets_count():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = QueueManager(Path(tmpdir))
        item = QueueItem(id=generate_id("tst"), type="t", created_at=timestamp(), priority=1, payload={}, status="", max_retries=1)
        asyncio.run(queue.enqueue(item))
        asyncio.run(queue.dequeue(item.id))
        asyncio.run(queue.fail(item.id))  # -> failed (max_retries=1)
        assert queue.counts()["failed"] == 1

        asyncio.run(queue.requeue_failed(item.id))
        assert queue.counts()["failed"] == 0
        assert queue.counts()["pending"] == 1
        path = queue._path(queue.pending_dir, item.id)
        with open(path) as f:
            data = json.load(f)
        assert data["retry_count"] == 0
        assert data["status"] == "pending"

def test_discard_failed():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = QueueManager(Path(tmpdir))
        item = QueueItem(id=generate_id("tst"), type="t", created_at=timestamp(), priority=1, payload={}, status="", max_retries=1)
        asyncio.run(queue.enqueue(item))
        asyncio.run(queue.dequeue(item.id))
        asyncio.run(queue.fail(item.id))
        assert queue.counts()["failed"] == 1

        asyncio.run(queue.discard_failed(item.id))
        assert queue.counts()["failed"] == 0

if __name__ == "__main__":
    tests = [
        test_enqueue_dequeue,
        test_acknowledge,
        test_fail_increment_and_persist,
        test_fail_max_retries,
        test_list_pending_sort,
        test_list_pending_type_filter,
        test_requeue_failed_resets_count,
        test_discard_failed
    ]
    for t in tests:
        t()
    print(f"{len(tests)}/{len(tests)} PASS")
