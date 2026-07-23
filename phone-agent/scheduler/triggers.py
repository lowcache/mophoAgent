"""Pure time logic for the scheduler: cron matching, interval/event triggers.

No I/O, no subprocess, stdlib only — the whole module is testable without a
device and imports cleanly with nothing installed.
"""

import time
from dataclasses import dataclass

_MINUTE, _HOUR, _DOM, _MONTH, _DOW = range(5)
_BOUNDS = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))


def _parse_field(field_str: str, min_val: int, max_val: int) -> set[int]:
    """Parse one cron field into its matching integers; empty set = invalid."""
    result: set[int] = set()
    for part in field_str.split(","):
        step = 1
        if "/" in part:
            part, _, step_str = part.partition("/")
            try:
                step = int(step_str)
            except ValueError:
                return set()
            if step <= 0:
                return set()

        if part == "*":
            start, end = min_val, max_val
        elif "-" in part.lstrip("-"):
            head, _, tail = part.partition("-")
            try:
                start, end = int(head), int(tail)
            except ValueError:
                return set()
        else:
            try:
                start = end = int(part)
            except ValueError:
                return set()

        if start < min_val or end > max_val or start > end:
            return set()
        result.update(range(start, end + 1, step))
    return result


def _parse_cron(expression: str) -> list[set[int]] | None:
    """All five parsed fields, or None if the expression is unusable."""
    fields = expression.split()
    if len(fields) != 5:
        return None
    parsed = [_parse_field(f, lo, hi) for f, (lo, hi) in zip(fields, _BOUNDS)]
    if not all(parsed):
        return None
    parsed[_DOW] = {0 if d == 7 else d for d in parsed[_DOW]}
    return parsed


def _day_matches(parsed: list[set[int]], expression: str, tm) -> bool:
    """POSIX day rule: when BOTH day-of-month and day-of-week are restricted
    the match is their OR, not their AND."""
    fields = expression.split()
    dom_restricted = fields[_DOM] != "*"
    dow_restricted = fields[_DOW] != "*"
    # tm_wday is Mon=0..Sun=6; cron is Sun=0..Sat=6.
    dow = 0 if tm.tm_wday == 6 else tm.tm_wday + 1
    in_dom = tm.tm_mday in parsed[_DOM]
    in_dow = dow in parsed[_DOW]
    if dom_restricted and dow_restricted:
        return in_dom or in_dow
    if dom_restricted:
        return in_dom
    if dow_restricted:
        return in_dow
    return True


def cron_match(expression: str, when: float) -> bool:
    """Evaluate a 5-field POSIX cron expression against a local timestamp.
    A malformed expression returns False rather than raising."""
    parsed = _parse_cron(expression)
    if parsed is None:
        return False
    try:
        tm = time.localtime(when)
    except (OverflowError, OSError, ValueError):
        return False
    if (tm.tm_min not in parsed[_MINUTE] or tm.tm_hour not in parsed[_HOUR]
            or tm.tm_mon not in parsed[_MONTH]):
        return False
    return _day_matches(parsed, expression, tm)


@dataclass
class Trigger:
    """Configuration and state for one task's firing rule."""
    type: str
    interval_seconds: int = 0
    offset_seconds: int = 0
    expression: str = ""
    event_name: str = ""
    last_fired: float = 0.0


def _num(spec: dict, key: str) -> float:
    """Config comes from an operator-edited JSON file, so a string or null
    where a number belongs must not raise out of the scheduler's reload."""
    v = spec.get(key, 0)
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def make_trigger(spec: dict, now: float | None = None) -> Trigger:
    """Build a Trigger from a config dict, normalizing the interval/offset
    key spellings. An unknown type is preserved verbatim and simply never
    fires from time."""
    if now is None:
        now = time.time()
    t_type = spec.get("type", "unknown")

    if t_type == "interval":
        interval = int(_num(spec, "interval_seconds")
                       + _num(spec, "interval_minutes") * 60
                       + _num(spec, "interval_hours") * 3600
                       + _num(spec, "interval_days") * 86400)
        # A 0 interval would fire every single tick forever.
        if interval <= 0:
            interval = 60
        offset = int(_num(spec, "offset_seconds") + _num(spec, "offset_minutes") * 60)
        # Seed last_fired so the FIRST firing lands `offset` from now; steady
        # state is a pure interval.
        return Trigger(type="interval", interval_seconds=interval,
                       offset_seconds=offset, last_fired=now + offset - interval)

    if t_type == "cron":
        return Trigger(type="cron", expression=str(spec.get("expression", "")))
    if t_type == "event":
        return Trigger(type="event", event_name=str(spec.get("event_name", "")))
    return Trigger(type=str(t_type))


class TriggerManager:
    """Holds every task's trigger and reports which are due."""

    def __init__(self) -> None:
        self.triggers: dict[str, Trigger] = {}
        self._pending_events: list[str] = []

    def register(self, task_id: str, trigger: Trigger) -> None:
        """Register (or replace) a task's trigger."""
        self.triggers[task_id] = trigger

    def unregister(self, task_id: str) -> None:
        """Remove a task; absent ids are ignored."""
        self.triggers.pop(task_id, None)
        self._pending_events = [t for t in self._pending_events if t != task_id]

    def clear(self) -> None:
        """Drop all triggers and pending events."""
        self.triggers.clear()
        self._pending_events.clear()

    def evaluate(self, now: float | None = None) -> list[str]:
        """Task ids due to fire, without duplicates; advances their last_fired."""
        if now is None:
            now = time.time()
        fired: list[str] = []
        seen: set[str] = set()

        def add(task_id: str) -> None:
            if task_id in seen:
                return
            seen.add(task_id)
            fired.append(task_id)
            trigger = self.triggers.get(task_id)
            if trigger is not None:
                trigger.last_fired = now

        for task_id in self._pending_events:
            add(task_id)
        self._pending_events.clear()

        for task_id, trigger in self.triggers.items():
            if task_id in seen:
                continue
            if trigger.type == "interval":
                if now - trigger.last_fired >= trigger.interval_seconds:
                    add(task_id)
            elif trigger.type == "cron":
                # The loop ticks more often than once a minute; a cron slot
                # must fire at most once per minute.
                if now - trigger.last_fired >= 60 and cron_match(trigger.expression, now):
                    add(task_id)
        return fired

    def fire_event(self, event_name: str) -> list[str]:
        """Queue every task listening for `event_name`; returns the ids queued.
        Executes nothing — the next evaluate() returns them."""
        queued = []
        for task_id, trigger in self.triggers.items():
            if (trigger.type == "event" and trigger.event_name == event_name
                    and task_id not in self._pending_events):
                self._pending_events.append(task_id)
                queued.append(task_id)
        return queued

    def next_fire_time(self, task_id: str, now: float | None = None) -> float | None:
        """Timestamp of the next firing, or None for event/unknown/unregistered."""
        trigger = self.triggers.get(task_id)
        if trigger is None:
            return None
        if trigger.type == "interval":
            return trigger.last_fired + trigger.interval_seconds
        if trigger.type != "cron":
            return None

        parsed = _parse_cron(trigger.expression)
        if parsed is None:
            return None
        if now is None:
            now = time.time()

        # Step by DAY, not by minute: a minute-by-minute scan over the 366-day
        # horizon is ~527k cron evaluations, which blocks the event loop for
        # seconds on an annual (or never-matching) expression.
        start = int(now) + (60 - int(now) % 60)
        times = sorted((h, m) for h in parsed[_HOUR] for m in parsed[_MINUTE])
        for offset_days in range(367):
            probe = time.localtime(start + offset_days * 86400)
            if probe.tm_mon in parsed[_MONTH] and _day_matches(parsed, trigger.expression, probe):
                for hour, minute in times:
                    ts = time.mktime((probe.tm_year, probe.tm_mon, probe.tm_mday,
                                      hour, minute, 0, 0, 0, -1))
                    if ts >= start:
                        return ts
        return None
