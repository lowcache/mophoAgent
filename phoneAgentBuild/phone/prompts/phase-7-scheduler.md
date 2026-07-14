# Phase 7: Subconscious Scheduler

**Target Agent:** Claude Code (phone, Termux)
**Commit message:** `feat(phone-mcp): subconscious scheduler with event-driven task loop`

---

## What You Are Building

An event-driven task scheduler that runs on the phone while the laptop is asleep. It defines tasks, triggers (time-based and event-based), and executes them. Results are logged locally and optionally queued for delivery to the laptop (via Phase 6's queue).

This is not a cron replacement. It's a lightweight agent event loop: when a trigger fires, the scheduler evaluates conditions, dispatches the appropriate task (via MCP tools or Termux commands), logs the result, and schedules the next check.

---

## Prerequisites

Phase 0 (server), Phase 1 (NPU), Phase 5 (notify), Phase 6 (queue for offline delivery).

---

## File Structure

```
~/phone-agent/
├── scheduler/
│   ├── __init__.py
│   ├── engine.py                 # NEW: scheduler event loop
│   ├── tasks.py                  # NEW: task definitions
│   ├── triggers.py               # NEW: trigger sources (cron, event, sensor)
├── config/
│   ├── scheduler_tasks.json      # NEW: user-configured task definitions
├── tools/
│   ├── scheduler_start.py        # NEW: phone.scheduler.start
│   ├── scheduler_stop.py         # NEW: phone.scheduler.stop
│   ├── scheduler_status.py       # NEW: phone.scheduler.status
│   ├── scheduler_add_task.py     # NEW: phone.scheduler.add_task
│   ├── scheduler_remove_task.py  # NEW: phone.scheduler.remove_task
```

---

## Implementation Spec

### config/scheduler_tasks.json — Default Task Definitions

```json
{
  "tasks": [
    {
      "id": "flake_check",
      "name": "Flake Update Check",
      "description": "Poll the GitHub API for nixpkgs channel movement (no nix on the phone). Result is queued for the laptop agent.",
      "trigger": {
        "type": "interval",
        "interval_hours": 6,
        "offset_minutes": 15
      },
      "action": {
        "type": "shell",
        "command": "curl -s -H 'Accept: application/vnd.github+json' https://api.github.com/repos/NixOS/nixpkgs/commits/nixos-unstable | jq -r .sha",
        "laptop_required": false
      },
      "conditions": {
        "battery_min_pct": 20,
        "wifi_only": true
      },
      "notify_on": ["success", "failure"],
      "enabled": true
    },
    {
      "id": "model_preload",
      "name": "Ollama Model Preload",
      "description": "List the laptop's Ollama models via its HTTP API (D3: no SSH). If unreachable, queue a check request for next laptop wake.",
      "trigger": {
        "type": "cron",
        "expression": "0 2 * * *"
      },
      "action": {
        "type": "shell",
        "command": "curl -sf --max-time 10 http://volnix.<tailnet>.ts.net:11434/api/tags",
        "laptop_required": true
      },
      "conditions": {
        "battery_min_pct": 50,
        "charging_required": true,
        "wifi_only": true
      },
      "notify_on": ["failure"],
      "enabled": true
    },
    {
      "id": "health_check",
      "name": "Laptop Health Check",
      "description": "Probe the laptop's Ollama HTTP endpoint to verify it's alive (the phone cannot MCP-call the laptop). Log reachability.",
      "trigger": {
        "type": "interval",
        "interval_minutes": 30
      },
      "action": {
        "type": "shell",
        "command": "curl -sf --max-time 5 http://volnix.<tailnet>.ts.net:11434/api/version",
        "laptop_required": true
      },
      "conditions": {
        "battery_min_pct": 10
      },
      "notify_on": ["failure"],
      "enabled": true
    },
    {
      "id": "log_cleanup",
      "name": "Ingest Log Cleanup",
      "description": "Remove ingest files older than 30 days to prevent storage bloat.",
      "trigger": {
        "type": "interval",
        "interval_days": 7
      },
      "action": {
        "type": "shell",
        "command": "find ~/ingest/processed -name '*.json' -mtime +30 -delete && find ~/ingest/audio -name '*.wav' -mtime +30 -delete && find ~/ingest/images -name '*.jpg' -mtime +30 -delete"
      },
      "conditions": {
        "battery_min_pct": 30
      },
      "notify_on": ["failure"],
      "enabled": true
    },
    {
      "id": "location_log",
      "name": "Geofence Change Detect",
      "description": "Check current location every 15 minutes. If geofence changed, log the transition for the laptop agent.",
      "trigger": {
        "type": "interval",
        "interval_minutes": 15
      },
      "action": {
        "type": "sensor",
        "tool": "phone.sensor.read_gps",
        "params": { "timeout_sec": 3 }
      },
      "conditions": {},
      "notify_on": [],
      "enabled": true
    }
  ]
}
```

### triggers.py — Trigger Types

```python
@dataclass
class Trigger:
    type: str                       # "interval", "cron", "event", "sensor_threshold"
    
@dataclass
class IntervalTrigger(Trigger):
    type = "interval"
    interval_seconds: int           # Base interval
    offset_seconds: int = 0         # One-time phase offset: seeds the FIRST firing only
    last_fired: float = 0           # Unix timestamp; initialized to now + offset_seconds - interval_seconds

@dataclass
class CronTrigger(Trigger):
    type = "cron"
    expression: str                 # cron expression: "0 */6 * * *"

@dataclass
class EventTrigger(Trigger):
    type = "event"
    event_name: str                 # "boot", "capture_complete", "laptop_reconnect", "sensor_threshold"

class TriggerManager:
    def __init__(self):
        self.triggers: dict[str, Trigger] = {}

    def evaluate(self) -> list[str]:
        """Check all triggers. Return list of task IDs that should fire."""
        now = time.time()
        fired = []
        for task_id, trigger in self.triggers.items():
            if trigger.type == "interval":
                # offset_seconds only seeds the initial last_fired; steady state is pure interval
                if now - trigger.last_fired >= trigger.interval_seconds:
                    fired.append(task_id)
                    trigger.last_fired = now
            elif trigger.type == "cron":
                if cron_match(trigger.expression, now):
                    # Only fire once per cron cycle
                    if now - trigger.last_fired >= 60:  # Debounce 60s
                        fired.append(task_id)
                        trigger.last_fired = now
            elif trigger.type == "event":
                # Events are triggered externally via fire_event()
                pass
        return fired

    def fire_event(self, event_name: str):
        """Externally trigger all tasks listening for this event."""
        for task_id, trigger in self.triggers.items():
            if trigger.type == "event" and trigger.event_name == event_name:
                self._pending_events.append(task_id)
```

### engine.py — Scheduler Event Loop

```python
class SchedulerEngine:
    def __init__(self, queue_mgr: QueueManager):
        self.tasks = load_tasks("config/scheduler_tasks.json")
        self.triggers = TriggerManager()
        self.queue = queue_mgr
        self.running = False

    async def start(self):
        self.running = True
        while self.running:
            # 1. Evaluate triggers
            fired_task_ids = self.triggers.evaluate()
            
            for task_id in fired_task_ids:
                task = self.tasks[task_id]
                
                # 2. Check conditions
                if not self._check_conditions(task.conditions):
                    continue  # Skip if conditions not met

                # 3. Execute task
                try:
                    result = await self._execute_task(task)
                    self._log_result(task_id, result)  # writes JSON to ~/ingest/processed/scheduled/

                    # 4. Notify on conditions
                    if result["status"] == "success" and "success" in task.notify_on:
                        await send_notification(f"Task completed: {task.name}", result.get("summary", ""))
                    elif result["status"] != "success" and "failure" in task.notify_on:
                        await send_notification(f"Task failed: {task.name}", result.get("error", "Unknown error"))

                    # 5. Queue for laptop delivery if offline
                    if not await is_laptop_online():
                        self.queue.enqueue(QueueItem(
                            id=generate_id(),
                            type="schedule_result",
                            created_at=timestamp(),
                            priority=1,
                            payload={"task_id": task_id, "result": result},
                            status="pending"
                        ))

                except Exception as e:
                    self._log_error(task_id, str(e))

            # Wait before next cycle
            await asyncio.sleep(30)  # Check every 30 seconds

    def _check_conditions(self, conditions: dict) -> bool:
        """Check if conditions are met before executing a task."""
        if conditions.get("battery_min_pct"):
            state = get_phone_state()
            if state["battery_pct"] < conditions["battery_min_pct"]:
                return False
        if conditions.get("charging_required"):
            state = get_phone_state()
            if not state["charging"]:
                return False
        if conditions.get("wifi_only"):
            modem = get_modem_state()
            if modem["network_type"] != "WiFi":
                return False
        return True

    async def _execute_task(self, task) -> dict:
        """Execute a task's action."""
        if task.action.type == "shell":
            return await termux_exec(task.action.command)
        elif task.action.type == "mcp_tool":
            if task.action.target == "laptop":
                if not await is_laptop_online():
                    return {"status": "skipped", "reason": "laptop offline"}
                # Forward tool call to laptop MCP
                return await laptop_mcp_call(task.action.tool, task.action.params)
            else:
                return await local_tool_call(task.action.tool, task.action.params)
        elif task.action.type == "sensor":
            return await local_tool_call(task.action.tool, task.action.params)
        return {"status": "error", "error": f"Unknown action type: {task.action.type}"}
```

### Tools

**phone.scheduler.start** — Start the scheduler loop.
**phone.scheduler.stop** — Stop the scheduler loop.
**phone.scheduler.status** — Return current scheduler state + next scheduled tasks.
**phone.scheduler.add_task** — Add a new task to the schedule.
**phone.scheduler.remove_task** — Remove a task by ID.

---

## Test Procedure

1. Start scheduler:
   ```bash
   echo '{"jsonrpc":"2.0","method":"tools/call","id":14,"params":{"name":"phone.scheduler.start","arguments":{}}}' | ...
   ```

2. Check status:
   ```bash
   echo '{"jsonrpc":"2.0","method":"tools/call","id":15,"params":{"name":"phone.scheduler.status","arguments":{}}}' | ...
   ```
   → Shows enabled tasks with next fire times

3. Test a fast task: Set `log_cleanup` interval to 1 minute. Wait 60s. Verify it fires (result JSON in `~/ingest/processed/scheduled/`).

4. Test condition skip: Set battery_min_pct to 90. Disconnect charger. Verify task is skipped.

---

## Acceptance Criteria

- [ ] Scheduler starts and runs tasks on their configured intervals
- [ ] Conditions (battery, charging, wifi_only) correctly gate task execution
- [ ] Tasks that require laptop are skipped when laptop is offline
- [ ] Results are logged to `~/ingest/processed/scheduled/` directory
- [ ] Notifications fire on success/failure based on task config
- [ ] `phone.scheduler.start/stop/status` work correctly
- [ ] `phone.scheduler.add_task` persists new task across server restart
- [ ] Scheduler respects power state: stops when battery < battery_min_pct
- [ ] Empty scheduler (no tasks) doesn't crash

---

## Guardrails

- **Scheduler does NOT use cron.** It's a Python asyncio event loop that checks triggers every 30s. This is more flexible than cron (conditions, event triggers) and doesn't require Android cron support.
- **Tasks are not guaranteed to fire exactly on time.** The 30s check cycle means tasks may fire up to 30s late. This is fine for maintenance tasks. If exact timing is needed, use the `phone.scheduler.add_task` with a one-shot trigger.
- **Battery conditions prevent battery drain.** Tasks only fire when battery is above the configured minimum. No task should drain the phone below the user's threshold.
- **Wifi-only tasks skip on cellular.** The `wifi_only` condition prevents mobile data usage for large downloads.
- **No task should ever drain the phone.** If battery < 5% and not charging, the scheduler enters emergency idle: all tasks are skipped, regardless of conditions, until charging is detected.

---

## Git Commit

```bash
git add -A
git commit -m "feat(phone-mcp): subconscious scheduler with event-driven task loop"
git tag phone-mcp-phase-7
git push origin phone
```

Rollback: `git revert HEAD`. Scheduler reverts. All other functionality unaffected.
