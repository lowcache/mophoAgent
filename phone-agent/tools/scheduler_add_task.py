"""phone.scheduler.add_task — define (or replace) a scheduled task."""

from scheduler.tasks import TaskError
from tools.scheduler_common import get_engine, set_mcp


def register(mcp):
    set_mcp(mcp)

    @mcp.tool(name="phone.scheduler.add_task")
    async def scheduler_add_task(id: str, name: str, trigger: dict,
                                 action: dict, conditions: dict | None = None,
                                 notify_on: list[str] | None = None,
                                 description: str = "",
                                 enabled: bool = True) -> dict:
        """Add a task and persist it, so it survives a server restart. An
        existing id is replaced. trigger: {"type":"interval",
        "interval_minutes":N} | {"type":"cron","expression":"0 2 * * *"} |
        {"type":"event","event_name":"boot"}. action: {"type":"shell",
        "command":...} (shell commands go through the shared blocklist and may
        use {laptop_host}/{ollama_port}) or {"type":"sensor"|"mcp_tool",
        "tool":"phone.sensor.read_gps","params":{...}}; add
        "laptop_required":true to skip it while the laptop is unreachable.
        conditions: battery_min_pct, charging_required, wifi_only. notify_on:
        any of success, failure. Returns task_id and next_fire. Errors:
        TASK_INVALID, SCHEDULER_FAILED."""
        spec = {"id": id, "name": name, "trigger": trigger, "action": action,
                "conditions": conditions or {}, "notify_on": notify_on or [],
                "description": description, "enabled": enabled}
        try:
            return get_engine().add_task(spec)
        except TaskError as e:
            return {"error": e.code, "message": e.message}
        except Exception as e:
            return {"error": "SCHEDULER_FAILED", "message": str(e)[:200]}
