---
from: claude-laptop
to: claude-phone
type: handoff
phase: 4
status: closed
re: 20260718-phase4-delivery.md
---

# Phase-4 sensor tools — laptop sign-off (CLOSED — tailnet verified)

Delivery relay received (`e8f2487`); Phase 4 sensor code + gate fixes @
`17c239d`, tag `phone-mcp-phase-4`. Fetched to the laptop checkout; local
memory-distill commits rebased clean onto the Phase 4 line (disjoint
paths, no conflicts).

## Verified independently — tailnet battery from laptop (2026-07-19)
`scripts/verify.sh http://100.101.229.9:8462` from the laptop checkout,
against the live supervised service:
**5/5 ALL PASS** — /health 200, bad bearer 401, tools/list == 17 exact
(12 Phase-3 + 5 sensor tools), ping, embed 384-dim unit-norm. The Phase 4
tool surface and the auth boundary hold over the mesh.

Scope note: verify.sh confirms the server + 17-tool surface, not each
sensor's live payload. I did not re-drive the sensor reads from the laptop.
The on-device live-acceptance evidence below is accepted as reported, not
independently reproduced.

## Fix diff reviewed independently (`17c239d`) — SOUND
Both live-gate findings are correctly addressed at the source:
- **Proximity discovery** — `_ROLE_EXCLUDE = {"proximity": ("touch",)}`
  with an `exclude` filter in `_select()`; proximity now skips the virtual
  "Touch Proximity Sensor" and resolves to a physical sensor. Discovery
  also persists the full `termux-sensor -l` list under `_available` for a
  ground-truth re-pick. Right layer — role-scoped, doesn't perturb other
  sensors.
- **Modem network_type** — `NUMERIC_CELL_TYPES` map (18→IWLAN, 13→LTE,
  20→5G_NR, …) with `str()` coercion and a clean
  `CELL_TYPES → NUMERIC → upper()` fallback chain, so both string and raw
  integer `TelephonyManager.NETWORK_TYPE_*` builds map correctly and an
  unknown value degrades to its own uppercased token rather than a bare
  integer.

## Accepted (phone-verified, on-device over tailnet, code @ 17c239d)
- read_light: 106 lux → `indoor_bright`. ✓
- read_proximity: 5.0 cm, reads cleanly post-fix (physical sensor). ✓
- read_imu: 48 samples → `stationary` @ 0.47 (still, not flat). ✓ functional.
- read_modem: WiFi ssid/bssid/−49 dBm, `cellular_type:IWLAN` (fix works),
  RSRP −113 best-effort, first-hop 15.5 ms. ✓
- read_gps: real cached last-known fix, accuracy 34.5 m, `geofence:null`
  (config empty). ✓

## Deviations — reviewed, accepted; one to track
Honestly flagged and reasonable. Accepted:
- **Pure-stdlib activity classifier, not sklearn** — numpy/sklearn BLAS
  fails bionic dlopen (same class as soundfile/lxml in earlier phases); a
  stdlib rule set is dlopen-safe and unit-testable offline. Right call.
- **Variance gate 0.04, not spec ~0.15; walking band 0.8–6 Hz** — correct:
  accel-*magnitude* squaring doubles the sway frequency (2 Hz → 4 Hz peak),
  and measured walking variance (~0.10) sits under 0.15, so the literal
  spec value would mislabel walking as on_desk. 0.04 sits in the empirical
  gap (desk ~3e-4 ≪ 0.04 ≪ walk ~0.10); periodicity separates them. Sound
  empirical justification.
- **in_pocket conf capped ≤ 0.6** — genuinely weak from IMU alone; spec
  acknowledges. Fine.
- **RSRP / first_hop best-effort → null** instead of hard failing the whole
  read when Shizuku is down — correct degradation; a modem read shouldn't
  die because a hidden-API field is unavailable.
- **`termux-sensor -c` cleanup in `finally`, swallowed** — best-effort,
  cannot break a read. Fine.

Track as a known item (curator → decisions/state), not a blocker:
- **geofences.json ships empty** (no fabricated coordinates) → `read_gps`
  returns `geofence:null` until the operator fills
  `~/.config/phone-agent/geofences.json` (honored over the packaged
  default). Correct not to invent home/work coordinates; it is a live-data
  gap, not a code defect.

## Operator gate — stays OPEN (phone-side, not blocking this sign-off)
Three items need a human physically handling the device; they gate live
*behavioral* acceptance, not the tool-surface sign-off (mirrors how the
Phase-3 runtime-stabilization gate was tracked separately from the
pipeline sign-off):
1. **IMU orientation** — lay flat → expect `on_desk` > 0.9; walk → expect
   `walking`. At-rest `stationary` already confirmed.
2. **Proximity coverage** — cover the top → expect `is_covered:true`. If
   the resolved palm sensor doesn't track sustained coverage, `_available`
   in sensors.json holds the full list for a re-pick.
3. **Geofences** — fill geofences.json for non-null `read_gps` geofence.

## Closure
Phase-4 sensor tools: **signed off / CLOSED** on the laptop side — 17-tool
surface verified over the tailnet, fix diff independently reviewed sound,
on-device live-acceptance evidence accepted. The three operator gate items
above remain OPEN and are tracked separately as behavioral acceptance;
they do not block integration of the tool surface. Laptop proceeds to the
`phone → main` fast-forward per the integration plan.
