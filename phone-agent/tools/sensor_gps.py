"""phone.sensor.read_gps — single-shot location read (low power).

Uses the cached last-known fix by default (D10: `-r last` is cached, not a
fresh GPS lock — the battery trade-off). A fresh fix would be
`termux-location -r once -p gps`."""

import json

from sensors.geofence import check_geofence
from tools.capture_common import CaptureError, run_cli


def register(mcp):
    @mcp.tool(name="phone.sensor.read_gps")
    async def read_gps(timeout_sec: int = 5) -> dict:
        """Single-shot GPS read via the cached last-known fix
        (termux-location -r last; low power per D10). Returns lat, lon,
        accuracy_m, and the matching named geofence (or null). Errors:
        GPS_TIMEOUT (no fix within timeout_sec), GPS_DISABLED (location
        services off)."""
        try:
            proc = await run_cli(["termux-location", "-r", "last"],
                                 timeout=max(timeout_sec, 1) + 5)
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

        return {
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
            "accuracy_m": round(float(loc.get("accuracy", 0.0)), 1),
            "geofence": check_geofence(float(lat), float(lon)),
        }
