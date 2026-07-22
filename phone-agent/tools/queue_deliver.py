"""phone.queue.deliver — deliver one pending item to the caller (laptop pulls)."""

from dataclasses import asdict

from tools.queue_common import get_queue_manager


def register(mcp):
    @mcp.tool(name="phone.queue.deliver")
    async def queue_deliver(item_id: str, acknowledge: bool = True) -> dict:
        """Deliver one pending queue item to the caller. The phone never pushes;
        returning the item IN this response IS the delivery. With
        acknowledge=true the item moves pending -> delivering -> delivered;
        with acknowledge=false it is left in delivering for a later confirm.
        Returns the item, status, and queue_remaining (pending count). Errors:
        ITEM_NOT_FOUND."""
        qm = get_queue_manager()
        try:
            item = await qm.dequeue(item_id)
        except FileNotFoundError:
            return {"error": "ITEM_NOT_FOUND", "message": item_id}
        if acknowledge:
            await qm.acknowledge(item_id)
            status = "delivered"
        else:
            status = "delivering"
        return {"item": asdict(item), "status": status,
                "queue_remaining": qm.counts()["pending"]}
