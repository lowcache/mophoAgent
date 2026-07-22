"""phone.queue.clear_failed — retry or delete a failed queue item."""

from tools.queue_common import get_queue_manager


def register(mcp):
    @mcp.tool(name="phone.queue.clear_failed")
    async def queue_clear_failed(item_id: str, action: str = "retry") -> dict:
        """Act on a failed queue item. action="retry" moves it back to pending
        with retry_count reset to 0; action="delete" discards it permanently.
        Returns status and queue_remaining_failed. Errors: BAD_ACTION,
        ITEM_NOT_FOUND."""
        if action not in ("retry", "delete"):
            return {"error": "BAD_ACTION",
                    "message": "action must be 'retry' or 'delete'"}
        qm = get_queue_manager()
        try:
            if action == "retry":
                await qm.requeue_failed(item_id)
                status = "retrying"
            else:
                await qm.discard_failed(item_id)
                status = "deleted"
        except FileNotFoundError:
            return {"error": "ITEM_NOT_FOUND", "message": item_id}
        return {"status": status,
                "queue_remaining_failed": qm.counts()["failed"]}
