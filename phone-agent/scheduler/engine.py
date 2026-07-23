"""The scheduler event loop.

One asyncio task ticks every `tick_sec`, asks the TriggerManager what is due,
gates each firing on live device conditions, runs the action, logs the result,
notifies per the task's `notify_on`, and queues the result for the laptop when
the laptop is unreachable.

Everything the engine touches is injected (shell, tool_call, notify, is_online,
queue, conditions) so the whole loop is testable without a device.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from scheduler.conditions import DeviceConditions
from scheduler.tasks import Task, TaskError, load_tasks, save_tasks, task_from_dict
from scheduler.triggers import TriggerManager, make_trigger

DEFAULT_TICK_SEC = 30.0
# Results kept per task for `scheduler.status`; the durable record is on disk.
_LAST_RESULTS = 1


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SchedulerEngine:
    def __init__(self, tasks_path: Path, log_dir: Path, *,
                 shell=None, tool_call=None, notify=None, is_online=None,
                 queue=None, conditions=None, tick_sec: float = DEFAULT_TICK_SEC,
                 expand=None):
        self.tasks_path = Path(tasks_path)
        self.log_dir = Path(log_dir)
        self._shell = shell
        self._tool_call = tool_call
        self._notify = notify
        self._is_online = is_online
        self._queue = queue
        self._expand = expand or (lambda s: s)
        self.conditions = conditions or DeviceConditions(shell)
        self.tick_sec = tick_sec

        self.tasks: dict[str, Task] = {}
        self.rejected: list[str] = []
        self.triggers = TriggerManager()
        self.running = False
        self._task: asyncio.Task | None = None
        self._last: dict[str, dict] = {}
        self.started_at: float | None = None
        self.ticks = 0

        self.reload()

    # --- task table -------------------------------------------------------

    def reload(self) -> None:
        """Load the task file and rebuild the trigger table from it."""
        self.tasks, self.rejected = load_tasks(self.tasks_path)
        self.triggers.clear()
        now = time.time()
        for task in self.tasks.values():
            if task.enabled:
                self.triggers.register(task.id, make_trigger(task.trigger, now))

    def add_task(self, spec: dict) -> dict:
        """Validate, persist, and register a task. Replaces an existing id."""
        task = task_from_dict(spec)          # raises TaskError
        self.tasks[task.id] = task
        save_tasks(self.tasks_path, self.tasks)
        self.triggers.unregister(task.id)
        if task.enabled:
            self.triggers.register(task.id, make_trigger(task.trigger, time.time()))
        return {"task_id": task.id, "enabled": task.enabled,
                "next_fire": self._next_fire_iso(task.id)}

    def remove_task(self, task_id: str) -> dict:
        if task_id not in self.tasks:
            raise TaskError("TASK_NOT_FOUND", f"no task with id {task_id}")
        del self.tasks[task_id]
        save_tasks(self.tasks_path, self.tasks)
        self.triggers.unregister(task_id)
        self._last.pop(task_id, None)
        return {"task_id": task_id, "removed": True}

    # --- lifecycle --------------------------------------------------------

    async def start(self) -> dict:
        if self.running:
            return {"status": "already_running", "tasks": len(self.tasks)}
        self.running = True
        self.started_at = time.time()
        self._task = asyncio.create_task(self._loop())
        return {"status": "started", "tasks": len(self.tasks),
                "tick_sec": self.tick_sec}

    async def stop(self) -> dict:
        if not self.running:
            return {"status": "not_running"}
        self.running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        return {"status": "stopped", "ticks": self.ticks}

    def status(self) -> dict:
        return {
            "running": self.running,
            "tick_sec": self.tick_sec,
            "ticks": self.ticks,
            "uptime_sec": (int(time.time() - self.started_at)
                           if self.started_at and self.running else 0),
            "task_count": len(self.tasks),
            "rejected": self.rejected,
            "tasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "enabled": t.enabled,
                    "trigger": t.trigger.get("type", "?"),
                    "next_fire": self._next_fire_iso(t.id),
                    "last_result": self._last.get(t.id),
                }
                for t in self.tasks.values()
            ],
        }

    def _next_fire_iso(self, task_id: str) -> str | None:
        ts = self.triggers.next_fire_time(task_id)
        if ts is None:
            return None
        return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def fire_event(self, event_name: str) -> list[str]:
        """Queue every task listening for `event_name`; the next tick runs them."""
        return self.triggers.fire_event(event_name)

    # --- the loop ---------------------------------------------------------

    async def _loop(self) -> None:
        while self.running:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                # A tick must never kill the loop; the per-task handler below
                # already catches task failures, so reaching here means a bug
                # in the loop itself and the next tick may well succeed.
                pass
            try:
                await asyncio.sleep(self.tick_sec)
            except asyncio.CancelledError:
                raise

    async def tick(self) -> list[dict]:
        """One scheduler cycle. Returns the results produced (for tests)."""
        self.ticks += 1
        fired = self.triggers.evaluate()
        if not fired:
            return []

        if await self.conditions.emergency_idle():
            # Emergency idle overrides every per-task condition. Triggers have
            # already advanced, so these firings are dropped, not deferred —
            # the point is to stop work, not to bank it up for later.
            return [self._record(tid, {"status": "skipped",
                                       "reason": "emergency idle: battery critical, not charging"})
                    for tid in fired]

        results = []
        for task_id in fired:
            task = self.tasks.get(task_id)
            if task is None or not task.enabled:
                continue
            try:
                result = await self._run_one(task)
            except Exception as e:
                result = {"status": "error", "error": f"{type(e).__name__}: {e}"[:200]}
            results.append(self._record(task_id, result))
        return results

    async def _run_one(self, task: Task) -> dict:
        met, reason = await self.conditions.check(task.conditions)
        if not met:
            return {"status": "skipped", "reason": reason}

        if task.action.laptop_required and not await self._online():
            return {"status": "skipped", "reason": "laptop offline"}

        result = await self._execute(task)

        await self._maybe_notify(task, result)
        if result.get("status") != "skipped":
            await self._maybe_queue(task, result)
        return result

    async def _execute(self, task: Task) -> dict:
        a = task.action
        if a.type == "shell":
            if self._shell is None:
                return {"status": "error", "error": "no shell dependency"}
            res = await self._shell(self._expand(a.command), timeout_sec=a.timeout_sec)
            code = res.get("exit_code")
            out = (res.get("stdout") or "").strip()
            return {
                "status": "success" if code == 0 else "failure",
                "exit_code": code,
                "summary": out[:200],
                "error": "" if code == 0 else ((res.get("stderr") or "").strip()[:200]
                                               or f"exited {code}"),
            }

        if a.type in ("sensor", "mcp_tool"):
            if a.type == "mcp_tool" and a.target == "laptop":
                # D3: the phone has no path to the laptop's MCP server (HTTP to
                # Ollama is the only laptop channel). Such a task is queued for
                # the laptop agent to run on its side rather than pretended.
                return {"status": "skipped",
                        "reason": "laptop MCP calls are unsupported (D3); queue it instead"}
            if self._tool_call is None:
                return {"status": "error", "error": "no tool dispatch dependency"}
            out = await self._tool_call(a.tool, dict(a.params))
            failed = isinstance(out, dict) and out.get("error")
            return {"status": "failure" if failed else "success",
                    "result": out,
                    "summary": (str(out.get("error")) if failed else "")[:200],
                    "error": str(out.get("error"))[:200] if failed else ""}

        return {"status": "error", "error": f"unknown action type: {a.type}"}

    async def _online(self) -> bool:
        if self._is_online is None:
            return False
        try:
            return bool(await self._is_online())
        except Exception:
            return False

    async def _maybe_notify(self, task: Task, result: dict) -> None:
        if self._notify is None:
            return
        status = result.get("status")
        if status == "success" and "success" in task.notify_on:
            body = result.get("summary") or "completed"
        elif status in ("failure", "error") and "failure" in task.notify_on:
            body = result.get("error") or "unknown error"
        else:
            return
        try:
            await self._notify(f"Task {status}: {task.name}", body)
        except Exception:
            pass

    async def _maybe_queue(self, task: Task, result: dict) -> None:
        """Queue the result for the laptop when it cannot be reached now."""
        if self._queue is None or await self._online():
            return
        try:
            await self._queue(task.id, result)
        except Exception:
            pass

    # --- durable log ------------------------------------------------------

    def _record(self, task_id: str, result: dict) -> dict:
        entry = {"task_id": task_id, "at": _utc(), **result}
        self._last[task_id] = entry
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            name = f"{task_id}-{time.strftime('%Y%m%dT%H%M%S', time.gmtime())}.json"
            path = self.log_dir / name
            tmp = path.parent / (path.name + ".tmp")
            with open(tmp, "w") as f:
                json.dump(entry, f)
            os.replace(tmp, path)
        except OSError:
            pass
        return entry
