"""Shared wiring for the Phase 7 scheduler tools (not a tool module —
tool_registry does not import it).

Owns the process-wide SchedulerEngine and supplies its injected dependencies:
Termux shell, in-process MCP tool dispatch, notifications, the shared D9
reachability ladder, and the Phase-6 queue.
"""

import json
import shutil

from config.settings import AGENT_DIR, CONFIG_DIR, INGEST_DIR
from msgqueue.manager import QueueItem, generate_id, timestamp
from scheduler.engine import SchedulerEngine
from scheduler.tasks import TASKS_NAME
from tools.queue_common import get_queue_manager
from tools.sys_common import SystemToolError, run_shell
from tools.voice_common import _laptop_config, get_detector, notify

OLLAMA_PORT = 11434
LOG_DIR = INGEST_DIR / "processed" / "scheduled"

# The live FastMCP instance, captured at tool-registration time so scheduled
# tasks can call other tools in-process without a loopback HTTP hop.
_mcp = None
_engine: SchedulerEngine | None = None


def set_mcp(mcp) -> None:
    global _mcp
    _mcp = mcp


def tasks_path():
    """Installed task file, seeded from the repo default on first use — the
    same auto-install the command blocklist uses. add_task must never write
    into the git working tree."""
    installed = CONFIG_DIR / TASKS_NAME
    if not installed.exists():
        default = AGENT_DIR / "config" / TASKS_NAME
        if default.exists():
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(default, installed)
    return installed


def expand(command: str) -> str:
    """Substitute {laptop_host} / {ollama_port} so task commands carry no
    hardcoded identity (the laptop address lives in config.json)."""
    cfg = _laptop_config()
    return (command.replace("{laptop_host}", cfg["laptop_host"])
                   .replace("{ollama_port}", str(OLLAMA_PORT)))


async def _shell(command: str, timeout_sec: float = 60.0) -> dict:
    """Termux bash with the shared blocklist. A refused or timed-out command
    is reported as a normal non-zero outcome so one bad task cannot raise
    through the scheduler loop."""
    try:
        return await run_shell(command, timeout_sec=timeout_sec)
    except SystemToolError as e:
        return {"stdout": "", "stderr": f"{e.code}: {e.message}", "exit_code": 1}


def _unwrap(out):
    """FastMCP.call_tool returns content blocks, a dict, or (blocks, dict)."""
    if isinstance(out, tuple) and len(out) == 2 and isinstance(out[1], dict):
        d = out[1]
        # convert_result wraps non-dict returns as {"result": ...}
        return d["result"] if set(d) == {"result"} and isinstance(d["result"], dict) else d
    if isinstance(out, dict):
        return out
    for block in out or []:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return {"text": text}
    return {}


async def _tool_call(name: str, params: dict) -> dict:
    if _mcp is None:
        return {"error": "TOOL_DISPATCH_UNAVAILABLE",
                "message": "scheduler was not given the MCP instance"}
    try:
        return _unwrap(await _mcp.call_tool(name, params or {}))
    except Exception as e:
        return {"error": "TOOL_CALL_FAILED", "message": f"{name}: {e}"[:200]}


async def _is_online() -> bool:
    return await get_detector().is_online()


async def _enqueue_result(task_id: str, result: dict) -> None:
    """Park a scheduled result for the laptop to collect on its next sync."""
    await get_queue_manager().enqueue(QueueItem(
        id=generate_id("sr"), type="schedule_result", created_at=timestamp(),
        priority=1, payload={"task_id": task_id, "result": result},
        status="pending"))


def get_engine() -> SchedulerEngine:
    global _engine
    if _engine is None:
        _engine = SchedulerEngine(
            tasks_path(), LOG_DIR,
            shell=_shell, tool_call=_tool_call, notify=notify,
            is_online=_is_online, queue=_enqueue_result, expand=expand)
    return _engine
