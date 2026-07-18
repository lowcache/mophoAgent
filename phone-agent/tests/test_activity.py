"""Standalone acceptance tests for sensors.activity (stdlib only).

Run from the phone-agent/ directory:  python3 tests/test_activity.py
Synthesizes IMU windows for three motion states and asserts the classifier's
label + confidence. Exits nonzero on any failure so it is CI-usable.
"""

import math
import os
import random
import sys

# Make `import sensors.activity` work when run as a bare script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sensors.activity import ActivityClassifier, classify

DT = 0.02  # 20 ms spacing => 50 Hz


def _on_desk_samples() -> list[dict]:
    """Flat phone: gravity on +z, tiny noise, gyro ~0."""
    random.seed(1)
    out = []
    for i in range(50):
        out.append({
            "accel": [random.gauss(0.0, 0.02),
                      random.gauss(0.0, 0.02),
                      9.81 + random.gauss(0.0, 0.02)],
            "gyro": [random.gauss(0.0, 0.001)] * 3,
            "timestamp": i * DT,
        })
    return out


def _walking_samples() -> list[dict]:
    """Gravity on z plus a ~2 Hz horizontal sway (~3 m/s^2) on x and y. The
    magnitude therefore oscillates at ~4 Hz (2x the sway) with high variance."""
    random.seed(2)
    out = []
    for i in range(50):
        t = i * DT
        sway = 3.0 * math.sin(2.0 * math.pi * 2.0 * t)
        out.append({
            "accel": [sway + random.gauss(0.0, 0.05),
                      sway + random.gauss(0.0, 0.05),
                      9.81 + random.gauss(0.0, 0.05)],
            "gyro": [0.0, 0.0, 0.0],
            "timestamp": t,
        })
    return out


def _upright_still_samples() -> list[dict]:
    """Upright phone: gravity on +y (tilted 90 deg from z), held still."""
    random.seed(3)
    out = []
    for i in range(50):
        out.append({
            "accel": [random.gauss(0.0, 0.02),
                      9.81 + random.gauss(0.0, 0.02),
                      random.gauss(0.0, 0.02)],
            "gyro": [0.0, 0.0, 0.0],
            "timestamp": i * DT,
        })
    return out


def _check(name: str, ok: bool, detail: str) -> bool:
    print(("PASS " if ok else "FAIL ") + name + "  " + detail)
    return ok


def main() -> int:
    results = []

    r = classify(_on_desk_samples())
    results.append(_check(
        "on_desk",
        r["inference"] == "on_desk" and r["confidence"] >= 0.9,
        repr(r)))

    r = classify(_walking_samples())
    results.append(_check(
        "walking",
        r["inference"] == "walking",
        repr(r)))

    # Exercise the class form here too, so both entry points are covered.
    r = ActivityClassifier().classify(_upright_still_samples())
    results.append(_check(
        "upright_still",
        r["inference"] in ("in_hand", "stationary"),
        repr(r)))

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
