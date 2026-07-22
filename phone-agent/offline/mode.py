from msgqueue.manager import QueueManager, QueueItem, generate_id, timestamp

class LocalOnlyMode:
    """
    Local-only mode toggle and orchestrator for enqueuing captures
    when the device is offline.
    """

    def __init__(self, queue: QueueManager, router, notify=None):
        self.queue = queue
        self.router = router
        self.notify = notify
        self.active = False

    async def enter(self) -> None:
        self.active = True
        self.router.force_local = True

    async def exit(self) -> None:
        self.active = False
        self.router.force_local = False
        if self.notify:
            await self.notify("Phone agent reconnected", "Syncing queued items")

    async def on_capture(self, capture_result: dict, priority: int = 1) -> QueueItem:
        item = QueueItem(
            id=generate_id("ing"),
            type="ingest",
            created_at=timestamp(),
            priority=priority,
            payload=capture_result,
            status="pending"
        )
        await self.queue.enqueue(item)
        return item
