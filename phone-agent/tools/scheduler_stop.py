"""phone.scheduler.stop — stop the subconscious task loop."""

from tools.scheduler_common import get_engine, set_mcp


def register(mcp):
    set_mcp(mcp)

    @mcp.tool(name="phone.scheduler.stop")
    async def scheduler_stop() -> dict:
        """Stop the scheduler event loop. In-flight task actions are
        cancelled; task definitions and logged results are untouched, so a
        later start resumes from the persisted task file. Returns status
        (stopped | not_running) and the number of ticks run. Errors:
        SCHEDULER_FAILED."""
        try:
            return await get_engine().stop()
        except Exception as e:
            return {"error": "SCHEDULER_FAILED", "message": str(e)[:200]}
