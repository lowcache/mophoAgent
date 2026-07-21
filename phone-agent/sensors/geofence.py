"""Geofence helpers for the Phase 4 location tools (pure stdlib, no termux)."""

import json
import math

from config.settings import AGENT_DIR, CONFIG_DIR


def haversine(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in meters between two lat/lon points."""
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_geofences() -> dict:
    """Load the operator's geofences (CONFIG_DIR/geofences.json) when
    present, else the packaged default. Returns {} for a missing or
    malformed file. Schema: {"home": {"lat": <f>, "lon": <f>,
    "radius_m": <n>}, ...}."""
    user = CONFIG_DIR / "geofences.json"
    path = user if user.exists() else AGENT_DIR / "config" / "geofences.json"
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def check_geofence(lat: float, lon: float) -> str | None:
    """Name of the first geofence whose center is within its radius_m of
    (lat, lon), else None. Malformed entries are skipped."""
    for name, fence in load_geofences().items():
        try:
            center_lat = fence["lat"]
            center_lon = fence["lon"]
            radius = fence["radius_m"]
            if haversine(lat, lon, center_lat, center_lon) <= radius:
                return name
        except (KeyError, TypeError, ValueError):
            continue
    return None


def evaluate_location(lat: float, lon: float) -> dict:
    """Single-pass geofence evaluation over one load_geofences() read.

    Returns {"geofence": <name of the first fence containing (lat,lon), or
    None>, "distance_m": <distance in metres to the NEAREST fence centre, or
    None when no valid fences are defined>}. Malformed entries are skipped."""
    inside: str | None = None
    nearest: float | None = None
    for name, fence in load_geofences().items():
        try:
            d = haversine(lat, lon, fence["lat"], fence["lon"])
            radius = fence["radius_m"]
        except (KeyError, TypeError, ValueError):
            continue
        if nearest is None or d < nearest:
            nearest = d
        if inside is None and d <= radius:
            inside = name
    return {"geofence": inside,
            "distance_m": round(nearest, 1) if nearest is not None else None}
