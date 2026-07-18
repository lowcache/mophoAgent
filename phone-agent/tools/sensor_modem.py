"""phone.sensor.read_modem — WiFi + cellular network state.

Core fields come from Termux:API (termux-wifi-connectioninfo,
termux-telephony-deviceinfo). Cellular RSRP needs a hidden API, so it is a
best-effort Shizuku/rish dumpsys read that returns null when Shizuku is
down. first_hop_latency_ms is a best-effort single ping. Only a total lack
of connectivity or a permission denial is a hard error."""

import json
import re

from tools.capture_common import CaptureError, run_cli
from tools.sensor_common import SensorError, run_sensor_cli

# termux-telephony network_type string -> canonical label.
CELL_TYPES = {
    "nr": "5G_NR", "lte": "LTE", "lte_ca": "LTE", "hspap": "HSPA+",
    "hspa": "HSPA", "hsdpa": "HSPA", "umts": "3G", "edge": "EDGE",
    "gprs": "GPRS", "cdma": "CDMA", "evdo_a": "EVDO", "iwlan": "IWLAN",
}
_NULL_BSSID = {"", "02:00:00:00:00:00", "00:00:00:00:00:00"}


def _json(proc) -> dict:
    try:
        d = json.loads(proc.stdout)
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _denied(proc) -> bool:
    text = (proc.stdout + proc.stderr).lower()
    return "permission" in text or "denied" in text


async def _cellular_rsrp():
    """Hidden-API RSRP via Shizuku/rish dumpsys; null if unreachable."""
    try:
        proc = await run_cli(
            ["rish", "-c", "dumpsys telephony.registry | grep -i rsrp"], timeout=6)
    except CaptureError:
        return None
    m = re.search(r"rsrp\s*[=:]?\s*(-?\d{2,3})", proc.stdout, re.IGNORECASE)
    return int(m.group(1)) if m else None


async def _first_hop_latency_ms():
    """Single ping to the default gateway (fallback 1.1.1.1); null on fail."""
    target = "1.1.1.1"
    try:
        route = await run_cli(["ip", "route", "get", "1.1.1.1"], timeout=4)
        m = re.search(r"via\s+(\d+\.\d+\.\d+\.\d+)", route.stdout)
        if m:
            target = m.group(1)
    except CaptureError:
        pass
    try:
        proc = await run_cli(["ping", "-c", "1", "-W", "1", target], timeout=4)
    except CaptureError:
        return None
    m = re.search(r"time[=<]\s*([\d.]+)\s*ms", proc.stdout)
    return round(float(m.group(1)), 1) if m else None


def register(mcp):
    @mcp.tool(name="phone.sensor.read_modem")
    async def read_modem(fields: list[str] | None = None) -> dict:
        """Read current network state — WiFi association (bssid, ssid,
        signal_dbm) and cellular (cellular_type, cellular_signal_rsrp,
        is_roaming) — plus first_hop_latency_ms. `fields`, if given, filters
        the returned keys. RSRP is null without a running Shizuku (hidden
        API). Errors: NO_CONNECTIVITY, PERMISSION_DENIED."""
        try:
            wifi_p = await run_sensor_cli(["termux-wifi-connectioninfo"])
            tel_p = await run_sensor_cli(["termux-telephony-deviceinfo"])
        except SensorError as e:
            return {"error": e.code, "message": e.message}
        if _denied(wifi_p) or _denied(tel_p):
            return {"error": "PERMISSION_DENIED",
                    "message": "grant Location to Termux:API for wifi/telephony info"}

        wifi = _json(wifi_p)
        tel = _json(tel_p)

        bssid = wifi.get("bssid")
        wifi_up = (wifi.get("supplicant_state") == "COMPLETED"
                   or (bssid and bssid not in _NULL_BSSID))

        raw_cell = (tel.get("network_type") or "").lower()
        cellular_type = CELL_TYPES.get(raw_cell, raw_cell.upper() or None)
        cell_up = bool(cellular_type) or tel.get("data_state") == "connected"

        if not wifi_up and not cell_up:
            return {"error": "NO_CONNECTIVITY", "message": "no WiFi or cellular connection"}

        out = {
            "bssid": bssid if wifi_up else None,
            "ssid": wifi.get("ssid") if wifi_up else None,
            "signal_dbm": wifi.get("rssi") if wifi_up else None,
            "network_type": "WiFi" if wifi_up else cellular_type,
            "cellular_type": cellular_type,
            "cellular_signal_rsrp": await _cellular_rsrp() if cell_up else None,
            "is_roaming": bool(tel.get("network_roaming", False)),
            "first_hop_latency_ms": await _first_hop_latency_ms(),
        }
        if fields:
            out = {k: v for k, v in out.items() if k in fields}
        return out
