"""Live device state for gating task execution.

Reads real battery/network state through an injected shell callable (the
Termux-API CLIs), cached briefly so a 30s tick with several tasks costs one
read, not one per task.

Unreadable state fails CLOSED for the task that asked about it: if the
operator declared `battery_min_pct` and we cannot read the battery, the guard
cannot be evaluated, so the guarded task does not run. Tasks that declare no
power/network condition are unaffected — a flaky Termux-API does not silence
the whole scheduler.
"""

import json
import time

# Below this, with no charger, nothing runs at all regardless of per-task
# conditions (charter guardrail: no task may drain the phone).
EMERGENCY_BATTERY_PCT = 5

_CACHE_TTL_SEC = 20.0
_UNKNOWN_SSIDS = {"", "<unknown ssid>", "0x", "null"}


class DeviceConditions:
    def __init__(self, shell, cache_ttl_sec: float = _CACHE_TTL_SEC):
        # shell(command, timeout_sec=...) -> {"stdout", "stderr", "exit_code"}
        self._shell = shell
        self._ttl = cache_ttl_sec
        self._cache: dict[str, tuple[float, dict]] = {}

    async def _read_json(self, key: str, command: str) -> dict | None:
        hit = self._cache.get(key)
        now = time.monotonic()
        if hit is not None and now - hit[0] < self._ttl:
            return hit[1]
        try:
            res = await self._shell(command, timeout_sec=10.0)
        except Exception:
            return None
        if res.get("exit_code") != 0:
            return None
        try:
            data = json.loads(res.get("stdout") or "")
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        self._cache[key] = (now, data)
        return data

    async def battery(self) -> dict:
        """{"percentage": int|None, "charging": bool|None, "status": str}."""
        d = await self._read_json("battery", "termux-battery-status")
        if d is None:
            return {"percentage": None, "charging": None, "status": "unknown"}
        pct = d.get("percentage")
        status = str(d.get("status", "")).upper()
        plugged = str(d.get("plugged", "")).upper()
        charging = (status in ("CHARGING", "FULL")
                    or (plugged not in ("", "UNPLUGGED", "PLUGGED_UNKNOWN")))
        return {"percentage": pct if isinstance(pct, int) else None,
                "charging": charging, "status": status or "unknown"}

    async def on_wifi(self) -> bool | None:
        """True/False, or None when the WiFi state cannot be read."""
        d = await self._read_json("wifi", "termux-wifi-connectioninfo")
        if d is None:
            return None
        # Termux reports supplicant_state COMPLETED with a real SSID only when
        # actually associated; a disconnected radio still returns an object.
        ssid = str(d.get("ssid", "")).strip().strip('"').lower()
        state = str(d.get("supplicant_state", "")).upper()
        if state and state != "COMPLETED":
            return False
        return ssid not in _UNKNOWN_SSIDS

    async def emergency_idle(self) -> bool:
        """True when the phone is critically low and not charging."""
        b = await self.battery()
        if b["percentage"] is None:
            return False        # unknown is not an emergency; per-task guards still apply
        return b["percentage"] < EMERGENCY_BATTERY_PCT and not b["charging"]

    async def check(self, conditions: dict) -> tuple[bool, str]:
        """(met, reason). reason is "" when met."""
        if not conditions:
            return True, ""

        want_pct = conditions.get("battery_min_pct")
        want_charging = conditions.get("charging_required")
        if want_pct is not None or want_charging:
            b = await self.battery()
            if b["percentage"] is None:
                return False, "battery state unavailable (condition fails closed)"
            if want_pct is not None and b["percentage"] < want_pct:
                return False, f"battery {b['percentage']}% < {want_pct}%"
            if want_charging and not b["charging"]:
                return False, "not charging"

        if conditions.get("wifi_only"):
            wifi = await self.on_wifi()
            if wifi is None:
                return False, "wifi state unavailable (condition fails closed)"
            if not wifi:
                return False, "not on wifi"

        return True, ""
