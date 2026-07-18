"""Shared helpers for the Phase 4 sensor tools (not a tool module —
tool_registry does not import it)."""

import json
import subprocess

from config.settings import CONFIG_DIR
from tools.capture_common import CaptureError, run_cli


class SensorError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


async def run_sensor_cli(cmd: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess:
    """run_cli, but re-raise its CaptureError (CLI_NOT_FOUND/CLI_TIMEOUT)
    as the SensorError the sensor tools expect."""
    try:
        return await run_cli(cmd, timeout=timeout)
    except CaptureError as e:
        raise SensorError(e.code, e.message)


# Logical role -> case-insensitive substring of the device-specific
# termux-sensor name. magnetometer is optional; it only lands in the map
# when a matching name is present.
_ROLE_SUBSTRINGS = {
    "accelerometer": "accelerometer",
    "gyroscope": "gyroscope",
    "light": "light",
    "proximity": "proximity",
    "magnetometer": "magnetic",
}


def _select(names: list[str], substr: str) -> str | None:
    """First name containing substr, preferring the calibrated, non-wakeup
    variant (no "uncalibrated"/"wake"); fall back to the first match."""
    matches = [n for n in names if substr in n.lower()]
    if not matches:
        return None
    for n in matches:
        low = n.lower()
        if "uncalibrated" not in low and "wake" not in low:
            return n
    return matches[0]


async def discover_sensors() -> dict[str, str]:
    """Enumerate this device's sensors (termux-sensor -l) and map logical
    roles to the device-specific name strings. Persists the map to
    CONFIG_DIR/sensors.json and returns it."""
    proc = await run_sensor_cli(["termux-sensor", "-l"])
    try:
        names = json.loads(proc.stdout).get("sensors", [])
    except json.JSONDecodeError:
        names = []
    mapping: dict[str, str] = {}
    for role, substr in _ROLE_SUBSTRINGS.items():
        name = _select(names, substr)
        if name is not None:
            mapping[role] = name
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "sensors.json").write_text(json.dumps(mapping, indent=2))
    return mapping


async def get_sensor_name(role: str) -> str:
    """Resolve a logical role to a device sensor name, using the cached
    CONFIG_DIR/sensors.json when it already knows the role, otherwise
    (re)discovering. Raises SENSOR_NOT_AVAILABLE if the device has none."""
    path = CONFIG_DIR / "sensors.json"
    mapping: dict = {}
    if path.exists():
        try:
            mapping = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            mapping = {}
    if role not in mapping:
        mapping = await discover_sensors()
    if role not in mapping:
        raise SensorError("SENSOR_NOT_AVAILABLE", f"no {role} sensor on this device")
    return mapping[role]


def _parse_readings(text: str) -> list[dict]:
    """termux-sensor streams concatenated pretty-printed JSON objects with
    no delimiter between them; walk them with raw_decode."""
    text = text.strip()
    decoder = json.JSONDecoder()
    readings: list[dict] = []
    idx, n = 0, len(text)
    while idx < n:
        while idx < n and text[idx].isspace():
            idx += 1
        if idx >= n:
            break
        try:
            obj, idx = decoder.raw_decode(text, idx)
        except json.JSONDecodeError:
            break
        readings.append(obj)
    return readings


def values_for(reading: dict, sensor_name: str) -> list[float] | None:
    """Tolerantly pull reading[sensor_name]["values"]; None if absent or
    malformed."""
    try:
        values = reading[sensor_name]["values"]
    except (KeyError, TypeError):
        return None
    if not isinstance(values, list):
        return None
    return values


async def read_sensors(names: list[str], count: int, interval_ms: int,
                       timeout: float | None = None) -> list[dict]:
    """Stream `count` readings from the named sensors at `interval_ms`
    spacing (termux-sensor -s ... -n ... -d ...) and parse the JSON stream.
    Releases the sensors (termux-sensor -c) in a finally. Errors:
    PERMISSION_DENIED, READ_ERROR (plus CLI_NOT_FOUND/CLI_TIMEOUT)."""
    if timeout is None:
        timeout = count * interval_ms / 1000 + 5.0
    cmd = ["termux-sensor", "-s", ",".join(names),
           "-n", str(count), "-d", str(interval_ms)]
    try:
        proc = await run_sensor_cli(cmd, timeout=timeout)
        combined = (proc.stdout + proc.stderr).lower()
        if "permission" in combined or "denied" in combined:
            raise SensorError("PERMISSION_DENIED",
                              "grant sensor permission to the Termux:API app")
        readings = _parse_readings(proc.stdout)
        if not readings:
            raise SensorError("READ_ERROR", "sensor returned no parseable readings")
        return readings
    finally:
        try:
            await run_sensor_cli(["termux-sensor", "-c"], timeout=5.0)
        except SensorError:
            pass
