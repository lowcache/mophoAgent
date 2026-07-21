"""Phase-5.5: evaluate_location() single-pass geofence eval (R3 distance +
existing inside-match). Pure logic — no termux, no GPS. Run: python -m pytest
tests/test_geofence.py  (or plain python tests/test_geofence.py)."""

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sensors import geofence  # noqa: E402

# A small fence in San Francisco; a point just inside and one ~1.1 km away.
FENCES = {"home": {"lat": 37.7749, "lon": -122.4194, "radius_m": 150}}
INSIDE = (37.7750, -122.4195)      # ~15 m from centre
OUTSIDE = (37.7849, -122.4194)     # ~1.1 km north


def _with(fences):
    return mock.patch.object(geofence, "load_geofences", return_value=fences)


def test_inside_returns_name_and_distance():
    with _with(FENCES):
        r = geofence.evaluate_location(*INSIDE)
    assert r["geofence"] == "home", r
    assert r["distance_m"] is not None and r["distance_m"] < 150, r


def test_outside_no_match_but_distance_reported():
    with _with(FENCES):
        r = geofence.evaluate_location(*OUTSIDE)
    assert r["geofence"] is None, r
    assert r["distance_m"] is not None and r["distance_m"] > 1000, r


def test_empty_map_nulls():
    with _with({}):
        r = geofence.evaluate_location(*INSIDE)
    assert r == {"geofence": None, "distance_m": None}, r


def test_malformed_entry_skipped_not_crashed():
    bad = {"broken": {"lat": 1.0}, "home": FENCES["home"]}  # missing lon/radius
    with _with(bad):
        r = geofence.evaluate_location(*INSIDE)
    assert r["geofence"] == "home", r
    assert r["distance_m"] is not None, r


def test_nearest_of_several():
    fences = {
        "far": {"lat": 40.0, "lon": -120.0, "radius_m": 100},
        "near": {"lat": 37.7760, "lon": -122.4194, "radius_m": 50},
    }
    with _with(fences):
        r = geofence.evaluate_location(*INSIDE)
    # nearest centre is "near"; inside neither radius -> geofence None
    assert r["geofence"] is None, r
    assert r["distance_m"] < 5000, r  # ~120 m to "near", not the 250+ km "far"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"PASS {fn.__name__}")
    print(f"{passed}/{len(fns)} passed")
