"""phone.scheduler.status — scheduler state and the task table."""

from tools.scheduler_common import get_engine, set_mcp


def register(mcp):
    set_mcp(mcp)

    @mcp.tool(name="phone.scheduler.status")
    async def scheduler_status() -> dict:
        """Report whether the loop is running, its tick interval and uptime,
        and every task with its enabled flag, trigger type, next fire time
        (UTC, null for event triggers) and last result. `rejected` lists task
        entries the config file defined but the scheduler refused to load.
        No input. Errors: SCHEDULER_FAILED."""
        try:
            return get_engine().status()
        except Exception as e:
            return {"error": "SCHEDULER_FAILED", "message": str(e)[:200]}
