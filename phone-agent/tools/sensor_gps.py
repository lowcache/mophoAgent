"""phone.sensor.read_gps — single-shot location read.

Defaults to the cached last-known fix (D10: `-r last` is cached, not a fresh
GPS lock — the battery trade-off). `fresh=True` forces a real lock
(`-r once -p gps`) for when the cache may be stale (e.g. a nomad's previous
city). Phase-5.5 prelude to the Phase-7 dynamic-home work."""

import json

from sensors.geofence import evaluate_location
from tools.capture_common import CaptureError, run_cli


def register(mcp):
    @mcp.tool(name="phone.sensor.read_gps")
    async def read_gps(timeout_sec: int = 5, fresh: bool = False,
                       max_accuracy_m: float | None = None) -> dict:
        """Single-shot GPS read. Default: cached last-known fix
        (termux-location -r last; low power per D10). fresh=True forces a real
        GPS lock (-r once -p gps; slower — a fresh lock may need line-of-sky and
        can legitimately GPS_TIMEOUT indoors). max_accuracy_m rejects a fix
        coarser than the given metres (GPS_INACCURATE). Returns lat, lon,
        accuracy_m, fresh, the matching named geofence (or null), and
        distance_m to the nearest fence centre (or null when none defined).
        Errors: GPS_TIMEOUT (no fix within timeout_sec), GPS_DISABLED (location
        services off), GPS_INACCURATE (fix coarser than max_accuracy_m)."""
        cmd = (["termux-location", "-r", "once", "-p", "gps"] if fresh
               else ["termux-location", "-r", "last"])
        # a fresh lock is slow — give GPS time to acquire beyond the caller budget
        budget = max(timeout_sec, 1) + (25 if fresh else 5)
        try:
            proc = await run_cli(cmd, timeout=budget)
        except CaptureError as e:
            if e.code == "CLI_TIMEOUT":
                return {"error": "GPS_TIMEOUT",
                        "message": f"no fix within {timeout_sec}s"}
            return {"error": "GPS_DISABLED", "message": e.message}

        text = (proc.stdout or "").strip()
        try:
            loc = json.loads(text)
        except json.JSONDecodeError:
            combined = (proc.stdout + proc.stderr).lower()
            if "disab" in combined or "not enabled" in combined or "provider" in combined:
                return {"error": "GPS_DISABLED", "message": "location services are off"}
            return {"error": "GPS_TIMEOUT", "message": "no location fix available"}

        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat is None or lon is None:
            return {"error": "GPS_TIMEOUT", "message": "no location fix available"}

        accuracy = round(float(loc.get("accuracy", 0.0)), 1)
        if max_accuracy_m is not None and accuracy > max_accuracy_m:
            return {"error": "GPS_INACCURATE",
                    "message": f"fix accuracy {accuracy}m exceeds max {max_accuracy_m}m",
                    "accuracy_m": accuracy}

        return {
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
            "accuracy_m": accuracy,
            "fresh": fresh,
            **evaluate_location(float(lat), float(lon)),
        }
