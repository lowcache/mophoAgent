"""Task definitions and their persistence.

Pure data + file I/O; no device access and no scheduling logic. The installed
task file lives in CONFIG_DIR (seeded from the repo default on first use, the
same marker-free auto-install the command blocklist uses) so `add_task` never
writes into the git working tree and survives a service restart.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

TASKS_NAME = "scheduler_tasks.json"

VALID_ACTIONS = ("shell", "sensor", "mcp_tool")
VALID_NOTIFY = ("success", "failure")


class TaskError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass
class Action:
    type: str
    command: str = ""
    tool: str = ""
    params: dict = field(default_factory=dict)
    target: str = "local"          # mcp_tool only: local | laptop
    laptop_required: bool = False
    timeout_sec: float = 60.0


@dataclass
class Task:
    id: str
    name: str
    action: Action
    trigger: dict = field(default_factory=dict)
    conditions: dict = field(default_factory=dict)
    notify_on: list[str] = field(default_factory=list)
    description: str = ""
    enabled: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["action"] = {k: v for k, v in d["action"].items()}
        return d


def task_from_dict(d: dict) -> Task:
    """Build a Task from a config entry. Raises TaskError on anything the
    scheduler could not act on — a half-valid task is worse than a rejected
    one, because it fires and then fails every cycle."""
    if not isinstance(d, dict):
        raise TaskError("TASK_INVALID", "task entry is not an object")
    tid = d.get("id")
    if not isinstance(tid, str) or not tid.strip():
        raise TaskError("TASK_INVALID", "task needs a non-empty string id")

    araw = d.get("action")
    if not isinstance(araw, dict):
        raise TaskError("TASK_INVALID", f"{tid}: action must be an object")
    atype = araw.get("type")
    if atype not in VALID_ACTIONS:
        raise TaskError("TASK_INVALID",
                        f"{tid}: action.type must be one of {VALID_ACTIONS}")
    if atype == "shell" and not str(araw.get("command", "")).strip():
        raise TaskError("TASK_INVALID", f"{tid}: shell action needs a command")
    if atype in ("sensor", "mcp_tool") and not str(araw.get("tool", "")).strip():
        raise TaskError("TASK_INVALID", f"{tid}: {atype} action needs a tool name")

    params = araw.get("params") or {}
    if not isinstance(params, dict):
        raise TaskError("TASK_INVALID", f"{tid}: action.params must be an object")

    action = Action(
        type=atype,
        command=str(araw.get("command", "")),
        tool=str(araw.get("tool", "")),
        params=params,
        target=str(araw.get("target", "local")),
        laptop_required=bool(araw.get("laptop_required", False)),
        timeout_sec=float(araw.get("timeout_sec", 60.0)),
    )

    trigger = d.get("trigger") or {}
    if not isinstance(trigger, dict) or not trigger.get("type"):
        raise TaskError("TASK_INVALID", f"{tid}: trigger needs a type")

    conditions = d.get("conditions") or {}
    if not isinstance(conditions, dict):
        raise TaskError("TASK_INVALID", f"{tid}: conditions must be an object")

    notify_on = [n for n in (d.get("notify_on") or []) if n in VALID_NOTIFY]

    return Task(
        id=tid,
        name=str(d.get("name") or tid),
        action=action,
        trigger=trigger,
        conditions=conditions,
        notify_on=notify_on,
        description=str(d.get("description", "")),
        enabled=bool(d.get("enabled", True)),
    )


def load_tasks(path: Path) -> tuple[dict[str, Task], list[str]]:
    """Read the task file. Returns (tasks_by_id, rejected_messages).

    A malformed FILE yields no tasks (an empty scheduler idles rather than
    crashing the server); a malformed TASK is dropped with its reason kept so
    `scheduler.status` can report it instead of failing silently."""
    rejected: list[str] = []
    try:
        raw = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {}, rejected
    except (OSError, json.JSONDecodeError) as e:
        return {}, [f"task file unreadable: {e}"]

    entries = raw.get("tasks") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        return {}, ["task file has no 'tasks' array"]

    tasks: dict[str, Task] = {}
    for entry in entries:
        try:
            task = task_from_dict(entry)
        except TaskError as e:
            rejected.append(e.message)
            continue
        if task.id in tasks:
            rejected.append(f"{task.id}: duplicate id, later entry ignored")
            continue
        tasks[task.id] = task
    return tasks, rejected


def save_tasks(path: Path, tasks: dict[str, Task]) -> None:
    """Persist atomically — a torn write would leave the scheduler with no
    tasks after the next restart."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp")
    payload = {"tasks": [t.to_dict() for t in tasks.values()]}
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, path)
