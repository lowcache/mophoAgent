import asyncio
from msgqueue.manager import QueueManager

class DeliveryProtocol:
    """
    Delivery protocol wrapper supporting timeout, retry, and acking.
    Returns ITEM_NOT_FOUND error objects instead of raising FileNotFoundError.
    """

    def __init__(self, queue: QueueManager, ack_timeout_sec: float = 10.0):
        self.queue = queue
        self.ack_timeout_sec = ack_timeout_sec

    async def deliver(self, item_id: str, deliver_fn, acknowledge: bool = True) -> dict:
        try:
            item = await self.queue.dequeue(item_id)
        except FileNotFoundError as e:
            return {"error": "ITEM_NOT_FOUND", "message": str(e)}

        success = False
        try:
            success = await asyncio.wait_for(deliver_fn(item), timeout=self.ack_timeout_sec)
        except TimeoutError:
            success = False

        if success and acknowledge:
            await self.queue.acknowledge(item_id)
            return {"status": "delivered", "item_id": item_id}
        else:
            await self.queue.fail(item_id)
            failed_path = self.queue._path(self.queue.failed_dir, item_id)
            if failed_path.exists():
                return {"status": "failed", "item_id": item_id, "retry_count": item.retry_count + 1}
            else:
                return {"status": "retry_scheduled", "item_id": item_id, "retry_count": item.retry_count + 1}

    async def deliver_all_pending(self, deliver_fn, types: list[str] | None = None, limit: int = 50) -> dict:
        pending_items = self.queue.list_pending(types=types, limit=limit)
        tally = {"delivered": 0, "retried": 0, "failed": 0}

        for item in pending_items:
            result = await self.deliver(item.id, deliver_fn)
            if result.get("status") == "delivered":
                tally["delivered"] += 1
            elif result.get("status") == "retry_scheduled":
                tally["retried"] += 1
            elif result.get("status") == "failed":
                tally["failed"] += 1

        return tally
