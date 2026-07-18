# Stabilization gate CLOSED + Phase 4 perms granted (2026-07-18)

Operator confirmed on-device: **Battery → Unrestricted** for Termux +
Termux:API, and **all Termux:API permissions granted** (incl. Sensors/Body
Sensors + Location).

## CRITICAL runtime-stabilization todo → effectively RESOLVED
Both mitigations for the 2026-07-17 idle-death incident are now live:
- Item #1: watchdog-install run, termux-job-scheduler job **462** pending. DONE.
- Item #2: Battery Unrestricted (Termux + Termux:API). DONE.
- Item #3: optional reboot confidence check (Termux:Boot → /health 200 →
  shared-URL lands in processed/summaries). Still pending, OPTIONAL.
Idle-death defense (external /health probe re-arming bootstrap + phantom
mitigation surviving OS app-kill) is in force. Curator: close the CRITICAL
stabilization todo; leave only the optional reboot check as a nicety.

## Phase 4 operator gate — item #1 satisfied
Sensors + Location perms granted → live sensor reads no longer return
PERMISSION_DENIED. Remaining Phase 4 gate: sensor-name discovery landing
correct accel/gyro/light/proximity names (proximity fix in progress —
"Touch Proximity Sensor" substring bug), and live acceptance reads
(desk→on_desk, walk→walking, modem SSID, gps, light levels, proximity
covered). Phase 4 NOT yet signed off; fix commits expected.
