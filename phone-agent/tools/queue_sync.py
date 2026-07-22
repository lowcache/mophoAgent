"""phone.queue.sync — list pending outbound queue items (does not deliver)."""

from tools.queue_common import get_queue_manager


def _summary(item) -> str:
    p = item.payload or {}
    s = p.get("summary") or p.get("full_text") or p.get("response") or item.type
    return str(s)[:120]


def register(mcp):
    @mcp.tool(name="phone.queue.sync")
    async def queue_sync(types: list[str] | None = None, limit: int = 50) -> dict:
        """List pending outbound queue items sorted by priority then age. This
        only reports — it does not deliver (the laptop agent pulls explicitly
        via phone.queue.deliver). Returns pending_count, delivered_count,
        failed_count, and item summaries."""
        qm = get_queue_manager()
        counts = qm.counts()
        items = qm.list_pending(types=types, limit=limit)
        return {
            "pending_count": counts["pending"],
            "delivered_count": counts["delivered"],
            "failed_count": counts["failed"],
            "items": [{"id": it.id, "type": it.type, "priority": it.priority,
                       "summary": _summary(it), "created_at": it.created_at}
                      for it in items],
        }
