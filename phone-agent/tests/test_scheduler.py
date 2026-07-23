"""Engine + task-persistence tests. No device, no network: every dependency
is injected. Run: python tests/test_scheduler.py"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scheduler.conditions import DeviceConditions
from scheduler.engine import SchedulerEngine
from scheduler.tasks import TaskError, load_tasks, save_tasks, task_from_dict


def _shell_task(tid="t1", **over):
    spec = {"id": tid, "name": "T", "trigger": {"type": "interval", "interval_seconds": 1},
            "action": {"type": "shell", "command": "echo hi"},
            "conditions": {}, "notify_on": ["success", "failure"]}
    spec.update(over)
    return spec


class FakeShell:
    """Stands in for run_shell AND for the Termux-API JSON reads."""

    def __init__(self, battery=80, charging=True, ssid="home", exit_code=0):
        self.battery, self.charging = battery, charging
        self.ssid, self.exit_code = ssid, exit_code
        self.commands = []

    async def __call__(self, command, timeout_sec=60.0):
        self.commands.append(command)
        if command == "termux-battery-status":
            if self.battery is None:
                return {"stdout": "", "stderr": "boom", "exit_code": 1}
            return {"stdout": json.dumps({
                "percentage": self.battery,
                "status": "CHARGING" if self.charging else "DISCHARGING",
                "plugged": "PLUGGED_AC" if self.charging else "UNPLUGGED"}),
                "stderr": "", "exit_code": 0}
        if command == "termux-wifi-connectioninfo":
            return {"stdout": json.dumps({"ssid": self.ssid,
                                          "supplicant_state": "COMPLETED"}),
                    "stderr": "", "exit_code": 0}
        return {"stdout": "hi", "stderr": "err" if self.exit_code else "",
                "exit_code": self.exit_code}


def _engine(tmp, shell, **kw):
    tasks_path = Path(tmp) / "scheduler_tasks.json"
    kw.setdefault("tick_sec", 0.01)
    return SchedulerEngine(tasks_path, Path(tmp) / "log", shell=shell,
                           conditions=DeviceConditions(shell, cache_ttl_sec=0),
                           **kw)


def _run(coro):
    return asyncio.run(coro)


# --- task table -----------------------------------------------------------

def test_rejects_invalid_task_without_killing_the_file():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "t.json"
        p.write_text(json.dumps({"tasks": [
            _shell_task("good"),
            {"id": "bad", "name": "B", "trigger": {"type": "interval"},
             "action": {"type": "shell"}},          # no command
        ]}))
        tasks, rejected = load_tasks(p)
        assert list(tasks) == ["good"]
        assert len(rejected) == 1 and "command" in rejected[0]


def test_missing_task_file_is_an_empty_scheduler():
    with tempfile.TemporaryDirectory() as tmp:
        tasks, rejected = load_tasks(Path(tmp) / "absent.json")
        assert tasks == {} and rejected == []


def test_add_task_persists_across_reload():
    with tempfile.TemporaryDirectory() as tmp:
        e = _engine(tmp, FakeShell())
        e.add_task(_shell_task("added"))
        e2 = _engine(tmp, FakeShell())
        assert "added" in e2.tasks


def test_remove_task_persists_and_unregisters():
    with tempfile.TemporaryDirectory() as tmp:
        e = _engine(tmp, FakeShell())
        e.add_task(_shell_task("gone"))
        e.remove_task("gone")
        assert "gone" not in e.tasks
        assert e.triggers.next_fire_time("gone") is None
        assert "gone" not in _engine(tmp, FakeShell()).tasks


def test_remove_unknown_task_raises_task_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        e = _engine(tmp, FakeShell())
        try:
            e.remove_task("nope")
            assert False, "expected TaskError"
        except TaskError as err:
            assert err.code == "TASK_NOT_FOUND"


# --- execution ------------------------------------------------------------

def test_task_runs_and_result_is_logged():
    with tempfile.TemporaryDirectory() as tmp:
        shell = FakeShell()
        e = _engine(tmp, shell)
        e.add_task(_shell_task("run", trigger={"type": "interval", "interval_seconds": 1}))
        results = _run(e.tick())
        assert results and results[0]["status"] == "success"
        assert "echo hi" in shell.commands
        logs = list((Path(tmp) / "log").glob("run-*.json"))
        assert len(logs) == 1
        assert json.loads(logs[0].read_text())["task_id"] == "run"


def test_nonzero_exit_is_failure_and_notifies():
    with tempfile.TemporaryDirectory() as tmp:
        seen = []

        async def notify(title, body):
            seen.append((title, body))

        e = _engine(tmp, FakeShell(exit_code=3), notify=notify)
        e.add_task(_shell_task("boom"))
        results = _run(e.tick())
        assert results[0]["status"] == "failure"
        assert len(seen) == 1
        assert seen[0][0] == "Task failure: T" and seen[0][1] == "err"


def test_battery_condition_skips():
    with tempfile.TemporaryDirectory() as tmp:
        e = _engine(tmp, FakeShell(battery=15, charging=False))
        e.add_task(_shell_task("low", conditions={"battery_min_pct": 50}))
        results = _run(e.tick())
        assert results[0]["status"] == "skipped" and "15%" in results[0]["reason"]


def test_charging_condition_skips_on_battery():
    with tempfile.TemporaryDirectory() as tmp:
        e = _engine(tmp, FakeShell(battery=90, charging=False))
        e.add_task(_shell_task("plug", conditions={"charging_required": True}))
        assert _run(e.tick())[0]["reason"] == "not charging"


def test_wifi_only_skips_off_wifi():
    with tempfile.TemporaryDirectory() as tmp:
        e = _engine(tmp, FakeShell(ssid="<unknown ssid>"))
        e.add_task(_shell_task("wifi", conditions={"wifi_only": True}))
        assert _run(e.tick())[0]["reason"] == "not on wifi"


def test_unreadable_battery_fails_closed_only_for_guarded_tasks():
    with tempfile.TemporaryDirectory() as tmp:
        e = _engine(tmp, FakeShell(battery=None))
        e.add_task(_shell_task("guarded", conditions={"battery_min_pct": 20}))
        e.add_task(_shell_task("unguarded"))
        by_id = {r["task_id"]: r for r in _run(e.tick())}
        assert by_id["guarded"]["status"] == "skipped"
        assert "unavailable" in by_id["guarded"]["reason"]
        assert by_id["unguarded"]["status"] == "success"


def test_emergency_idle_skips_everything():
    with tempfile.TemporaryDirectory() as tmp:
        e = _engine(tmp, FakeShell(battery=3, charging=False))
        e.add_task(_shell_task("any"))
        r = _run(e.tick())[0]
        assert r["status"] == "skipped" and "emergency idle" in r["reason"]


def test_laptop_required_skips_when_offline():
    with tempfile.TemporaryDirectory() as tmp:
        async def offline():
            return False
        e = _engine(tmp, FakeShell(), is_online=offline)
        e.add_task(_shell_task("lap", action={"type": "shell", "command": "echo x",
                                              "laptop_required": True}))
        assert _run(e.tick())[0]["reason"] == "laptop offline"


def test_result_is_queued_while_offline_and_not_when_online():
    with tempfile.TemporaryDirectory() as tmp:
        queued = []

        async def queue(task_id, result):
            queued.append(task_id)

        async def offline():
            return False

        async def online():
            return True

        e = _engine(tmp, FakeShell(), is_online=offline, queue=queue)
        e.add_task(_shell_task("q"))
        _run(e.tick())
        assert queued == ["q"]

        e2 = _engine(tmp, FakeShell(), is_online=online, queue=queue)
        e2.add_task(_shell_task("q2"))
        _run(e2.tick())
        assert queued == ["q"]


def test_command_placeholders_are_expanded():
    with tempfile.TemporaryDirectory() as tmp:
        shell = FakeShell()
        e = _engine(tmp, shell, expand=lambda c: c.replace("{laptop_host}", "volnix"))
        e.add_task(_shell_task("exp", action={"type": "shell",
                                              "command": "curl http://{laptop_host}/x"}))
        _run(e.tick())
        assert "curl http://volnix/x" in shell.commands


def test_sensor_action_dispatches_to_tool():
    with tempfile.TemporaryDirectory() as tmp:
        calls = []

        async def tool_call(name, params):
            calls.append((name, params))
            return {"lat": 1.0}

        e = _engine(tmp, FakeShell(), tool_call=tool_call)
        e.add_task(_shell_task("gps", action={"type": "sensor",
                                              "tool": "phone.sensor.read_gps",
                                              "params": {"timeout_sec": 3}}))
        r = _run(e.tick())[0]
        assert r["status"] == "success" and r["result"] == {"lat": 1.0}
        assert calls == [("phone.sensor.read_gps", {"timeout_sec": 3})]


def test_tool_error_dict_is_a_failure():
    with tempfile.TemporaryDirectory() as tmp:
        async def tool_call(name, params):
            return {"error": "GPS_TIMEOUT", "message": "no fix"}

        e = _engine(tmp, FakeShell(), tool_call=tool_call)
        e.add_task(_shell_task("gps", action={"type": "sensor", "tool": "x"}))
        r = _run(e.tick())[0]
        assert r["status"] == "failure" and r["error"] == "GPS_TIMEOUT"


def test_laptop_mcp_target_is_refused_not_faked():
    with tempfile.TemporaryDirectory() as tmp:
        async def tool_call(name, params):
            raise AssertionError("must not dispatch a laptop-targeted tool locally")

        e = _engine(tmp, FakeShell(), tool_call=tool_call)
        e.add_task(_shell_task("far", action={"type": "mcp_tool", "tool": "laptop.thing",
                                              "target": "laptop"}))
        assert _run(e.tick())[0]["status"] == "skipped"


def test_raising_dependency_does_not_break_the_tick():
    with tempfile.TemporaryDirectory() as tmp:
        async def boom(name, params):
            raise RuntimeError("dispatch exploded")

        e = _engine(tmp, FakeShell(), tool_call=boom)
        e.add_task(_shell_task("bad", action={"type": "sensor", "tool": "x"}))
        e.add_task(_shell_task("good"))
        by_id = {r["task_id"]: r for r in _run(e.tick())}
        assert by_id["bad"]["status"] == "error"
        assert by_id["good"]["status"] == "success"


def test_disabled_task_never_fires():
    with tempfile.TemporaryDirectory() as tmp:
        e = _engine(tmp, FakeShell())
        e.add_task(_shell_task("off", enabled=False))
        assert _run(e.tick()) == []


def test_empty_scheduler_ticks_without_crashing():
    with tempfile.TemporaryDirectory() as tmp:
        e = _engine(tmp, FakeShell())
        assert _run(e.tick()) == []
        assert e.status()["task_count"] == 0


def test_start_stop_lifecycle():
    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            e = _engine(tmp, FakeShell())
            e.add_task(_shell_task("loop"))
            assert (await e.start())["status"] == "started"
            assert (await e.start())["status"] == "already_running"
            await asyncio.sleep(0.05)
            out = await e.stop()
            assert out["status"] == "stopped" and out["ticks"] >= 1
            assert (await e.stop())["status"] == "not_running"
            assert e.status()["running"] is False
    _run(run())


def test_status_reports_next_fire_and_rejects():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "scheduler_tasks.json"
        p.write_text(json.dumps({"tasks": [_shell_task("ok"),
                                           {"id": "bad", "name": "b",
                                            "trigger": {"type": "interval"},
                                            "action": {"type": "nope"}}]}))
        e = _engine(tmp, FakeShell())
        st = e.status()
        assert st["task_count"] == 1 and len(st["rejected"]) == 1
        assert st["tasks"][0]["next_fire"].endswith("Z")


def test_event_task_fires_only_after_fire_event():
    with tempfile.TemporaryDirectory() as tmp:
        e = _engine(tmp, FakeShell())
        e.add_task(_shell_task("onboot", trigger={"type": "event", "event_name": "boot"}))
        assert _run(e.tick()) == []
        assert e.fire_event("boot") == ["onboot"]
        assert _run(e.tick())[0]["status"] == "success"
        assert _run(e.tick()) == []


def test_save_load_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "t.json"
        tasks = {"a": task_from_dict(_shell_task("a"))}
        save_tasks(p, tasks)
        back, rejected = load_tasks(p)
        assert rejected == [] and back["a"].action.command == "echo hi"


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    for t in TESTS:
        t()
    print(f"{len(TESTS)}/{len(TESTS)} PASS")
