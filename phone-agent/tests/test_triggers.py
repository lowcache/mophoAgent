import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scheduler.triggers import TriggerManager, make_trigger, cron_match

def test_cron_match():
    # 2023-01-01 is a Sunday (1st of month).
    t_0200 = time.mktime(time.strptime("2023-01-01 02:00:00", "%Y-%m-%d %H:%M:%S"))
    t_0201 = time.mktime(time.strptime("2023-01-01 02:01:00", "%Y-%m-%d %H:%M:%S"))
    t_0300 = time.mktime(time.strptime("2023-01-01 03:00:00", "%Y-%m-%d %H:%M:%S"))
    
    assert cron_match("0 2 * * *", t_0200)
    assert not cron_match("0 2 * * *", t_0201)
    assert not cron_match("0 2 * * *", t_0300)

def test_cron_step():
    t_00 = time.mktime(time.strptime("2023-01-01 01:00:00", "%Y-%m-%d %H:%M:%S"))
    t_15 = time.mktime(time.strptime("2023-01-01 01:15:00", "%Y-%m-%d %H:%M:%S"))
    t_30 = time.mktime(time.strptime("2023-01-01 01:30:00", "%Y-%m-%d %H:%M:%S"))
    t_45 = time.mktime(time.strptime("2023-01-01 01:45:00", "%Y-%m-%d %H:%M:%S"))
    t_07 = time.mktime(time.strptime("2023-01-01 01:07:00", "%Y-%m-%d %H:%M:%S"))
    
    assert cron_match("*/15 * * * *", t_00)
    assert cron_match("*/15 * * * *", t_15)
    assert cron_match("*/15 * * * *", t_30)
    assert cron_match("*/15 * * * *", t_45)
    assert not cron_match("*/15 * * * *", t_07)

def test_malformed_cron():
    t_00 = time.mktime(time.strptime("2023-01-01 01:00:00", "%Y-%m-%d %H:%M:%S"))
    assert not cron_match("not a cron", t_00)
    assert not cron_match("* * *", t_00)
    assert not cron_match("60 * * * *", t_00)
    assert not cron_match("* * * * 8", t_00)

def test_posix_or():
    t_1st_sun = time.mktime(time.strptime("2023-01-01 00:00:00", "%Y-%m-%d %H:%M:%S"))
    t_6th_fri = time.mktime(time.strptime("2023-01-06 00:00:00", "%Y-%m-%d %H:%M:%S"))
    t_2nd_mon = time.mktime(time.strptime("2023-01-02 00:00:00", "%Y-%m-%d %H:%M:%S"))
    
    assert cron_match("0 0 1 * 5", t_1st_sun)
    assert cron_match("0 0 1 * 5", t_6th_fri)
    assert not cron_match("0 0 1 * 5", t_2nd_mon)

def test_interval_offset():
    now = 1000000.0
    trigger = make_trigger({"type":"interval", "interval_hours":6, "offset_minutes":15}, now)
    assert trigger.interval_seconds == 21600
    tm = TriggerManager()
    tm.register("t1", trigger)

    assert "t1" not in tm.evaluate(now)
    assert "t1" not in tm.evaluate(now + 14 * 60)
    
    # DOES fire at now+16min
    eval_res = tm.evaluate(now + 16 * 60)
    assert "t1" in eval_res
    
    # then does not fire again immediately after
    assert "t1" not in tm.evaluate(now + 16 * 60 + 10)
    
    # and fires again 6h after that
    assert "t1" in tm.evaluate(now + 16 * 60 + 21600)

def test_interval_clamping():
    now = 1000000.0
    t2 = make_trigger({"type":"interval"}, now)
    assert t2.interval_seconds == 60
    t3 = make_trigger({"type":"interval", "interval_seconds": 0}, now)
    assert t3.interval_seconds == 60

def test_fire_event():
    now = 1000000.0
    tm = TriggerManager()
    tm.register("e1", make_trigger({"type":"event", "event_name":"boot"}))
    tm.register("e2", make_trigger({"type":"event", "event_name":"login"}))
    
    queued = tm.fire_event("boot")
    assert "e1" in queued
    assert "e2" not in queued
    
    eval1 = tm.evaluate(now)
    assert "e1" in eval1
    assert "e2" not in eval1
    
    eval2 = tm.evaluate(now)
    assert "e1" not in eval2

def test_no_duplicate_ids():
    now = 1000000.0
    tm = TriggerManager()
    # Force a task to be both pending and eligible via time
    tm.register("id1", make_trigger({"type":"interval", "interval_seconds": 60}, now - 100))
    tm._pending_events.append("id1")
    
    res = tm.evaluate(now)
    assert res.count("id1") == 1

def test_next_fire_time():
    now = 1000000.0
    tm = TriggerManager()
    trigger = make_trigger({"type":"interval", "interval_seconds": 60}, now)
    tm.register("t_int", trigger)
    tm.register("t_evt", make_trigger({"type":"event", "event_name":"boot"}))
    
    assert tm.next_fire_time("t_int", now) == trigger.last_fired + 60
    assert tm.next_fire_time("t_evt", now) is None
    assert tm.next_fire_time("unreg", now) is None

def test_unregister():
    now = 1000000.0
    tm = TriggerManager()
    tm.register("t_int", make_trigger({"type":"interval", "interval_seconds": 60}, now - 100))
    assert "t_int" in tm.evaluate(now)
    
    tm.unregister("t_int")
    assert "t_int" not in tm.evaluate(now + 100)

def test_next_fire_time_cron():
    # 2023-01-01 03:00 local -> next "0 2 * * *" is 2023-01-02 02:00 local.
    now = time.mktime(time.strptime("2023-01-01 03:00:00", "%Y-%m-%d %H:%M:%S"))
    tm = TriggerManager()
    tm.register("c", make_trigger({"type": "cron", "expression": "0 2 * * *"}, now))
    got = tm.next_fire_time("c", now)
    assert got == time.mktime(time.strptime("2023-01-02 02:00:00", "%Y-%m-%d %H:%M:%S"))

def test_next_fire_time_cron_same_day():
    now = time.mktime(time.strptime("2023-01-01 01:00:00", "%Y-%m-%d %H:%M:%S"))
    tm = TriggerManager()
    tm.register("c", make_trigger({"type": "cron", "expression": "0 2 * * *"}, now))
    assert tm.next_fire_time("c", now) == time.mktime(
        time.strptime("2023-01-01 02:00:00", "%Y-%m-%d %H:%M:%S"))

def test_next_fire_time_cron_malformed_is_none():
    now = 1000000.0
    tm = TriggerManager()
    tm.register("c", make_trigger({"type": "cron", "expression": "not a cron"}, now))
    start = time.monotonic()
    assert tm.next_fire_time("c", now) is None
    assert time.monotonic() - start < 1.0    # must bail, not scan a year of minutes

def test_make_trigger_tolerates_bad_types():
    t = make_trigger({"type": "interval", "interval_hours": "six"}, 1000000.0)
    assert t.interval_seconds == 60          # clamped, not a TypeError

if __name__ == "__main__":
    tests = [
        test_cron_match,
        test_cron_step,
        test_malformed_cron,
        test_posix_or,
        test_interval_offset,
        test_interval_clamping,
        test_fire_event,
        test_no_duplicate_ids,
        test_next_fire_time,
        test_unregister,
        test_next_fire_time_cron,
        test_next_fire_time_cron_same_day,
        test_next_fire_time_cron_malformed_is_none,
        test_make_trigger_tolerates_bad_types,
    ]
    for t in tests:
        t()
    print(f"{len(tests)}/{len(tests)} PASS")
