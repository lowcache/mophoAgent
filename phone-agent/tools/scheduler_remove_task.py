"""phone.scheduler.remove_task — delete a scheduled task."""

from scheduler.tasks import TaskError
from tools.scheduler_common import get_engine, set_mcp


def register(mcp):
    set_mcp(mcp)

    @mcp.tool(name="phone.scheduler.remove_task")
    async def scheduler_remove_task(task_id: str) -> dict:
        """Remove a task by id and persist the change; its trigger is
        unregistered immediately, so a running loop stops firing it without a
        restart. Already-logged results are kept. Returns task_id and removed.
        Errors: TASK_NOT_FOUND, SCHEDULER_FAILED."""
        try:
            return get_engine().remove_task(task_id)
        except TaskError as e:
            return {"error": e.code, "message": e.message}
        except Exception as e:
            return {"error": "SCHEDULER_FAILED", "message": str(e)[:200]}
