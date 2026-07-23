"""phone.scheduler.start — start the subconscious task loop."""

from tools.scheduler_common import get_engine, set_mcp


def register(mcp):
    set_mcp(mcp)

    @mcp.tool(name="phone.scheduler.start")
    async def scheduler_start(reload: bool = False) -> dict:
        """Start the scheduler event loop. It ticks every 30s, fires due
        triggers, gates each on live battery/charging/WiFi conditions, logs
        results to ~/ingest/processed/scheduled/, and queues them for the
        laptop while it is unreachable. Set reload=true to re-read the task
        file first. Returns status (started | already_running), task count and
        tick interval. Errors: SCHEDULER_FAILED."""
        try:
            engine = get_engine()
            if reload:
                engine.reload()
            return await engine.start()
        except Exception as e:
            return {"error": "SCHEDULER_FAILED", "message": str(e)[:200]}
