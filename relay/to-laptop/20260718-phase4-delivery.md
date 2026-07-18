---
type: delivery
from: claude-phone
date: 2026-07-18
subject: Phase 4 delivered — sensor tools, offline battery green
status: open
---

# Phase 4 delivery: sensor tools (tag `phone-mcp-phase-4`, fa9d214)

Five CPU-only single-shot sensor reads. **DEPLOYED and live-verified
on-device** 2026-07-18: native clone fast-forwarded to `5a092ad`, runit
respawn confirmed, `/health` 200, `tools/list` = 17, and all 5 sensor
tools return correct live data over the tailnet (5/5, see Live Acceptance
below). Includes fix commit `5a092ad` for two issues the live gate found.
Still pending: laptop `verify.sh` sign-off + two physical-orientation
operator checks.

## What shipped (5 new tools → 17 total)

- `tools/sensor_imu.py` — `phone.sensor.read_imu(sample_count, sample_interval_ms)`:
  accel+gyro burst via `termux-sensor` → on-device activity inference.
- `sensors/activity.py` — **pure-stdlib** (no numpy) heuristic classifier
  over six features (mean/variance of accel magnitude, DFT peak frequency,
  gravity angle, zero-crossing rate, HF/LF energy ratio) → on_desk /
  in_hand / in_pocket / walking / stationary / unknown. ~0.2 ms per
  50-sample classify.
- `tools/sensor_modem.py` — `phone.sensor.read_modem(fields)`: WiFi
  (bssid/ssid/signal_dbm) + cellular (type/rsrp/roaming) + first-hop ping.
- `tools/sensor_gps.py` — `phone.sensor.read_gps(timeout_sec)`: cached
  last-known fix (`termux-location -r last`, D10) + geofence tag.
- `tools/sensor_light.py`, `tools/sensor_proximity.py` — single reads,
  value→label mapping.
- `tools/sensor_common.py` — sensor-name discovery (`termux-sensor -l`),
  cached to `~/.config/phone-agent/sensors.json`; JSON-stream reader;
  `SensorError`.
- `sensors/geofence.py` + `config/geofences.json` (ships `{}`).
- Registry + `verify.sh` updated to the 17-tool set; `tests/test_activity.py`.

## Offline verification evidence (proot, 2026-07-18)

- `py_compile` clean on all Phase 4 files; `geofences.json` valid JSON.
- `tests/test_activity.py`: **3/3 PASS** — on_desk (conf 0.98), walking
  (0.86), upright-still→stationary (0.80). ~0.21 ms/classify (< 50 ms req).
- Import/register test with a stub MCP: all 5 tools register under the
  expected names; cross-module imports (imu→activity, gps→geofence,
  modem→sensor_common) resolve without the NPU/numpy chain.
- Note: field-name correctness of the termux-api JSON was cross-checked
  against DECISIONS.md D10 + the phase-4 spec (a tether/Gemini pass was
  attempted but did not return a usable verdict in print mode). Definitive
  validation is the on-device gate below.

## Live acceptance (2026-07-18, on-device over the tailnet)

Deployed via the validated pattern (proot commit → native
`git fetch /root/mophoAgent phone && merge --ff-only` → SIGTERM the server
pid, runit respawns on new code). All 5 tools driven over HTTP (server runs
termux-api natively — proot stays an HTTP client, D11 respected):

- **read_light**: 106 lux → `indoor_bright`. ✓
- **read_proximity**: 5.0 cm, `is_covered:false` (uncovered). ✓
- **read_imu**: 48 samples, inference `stationary` @ 0.47 (phone lying
  still but not flat). ✓ functional — the physical on_desk>0.9 / walking
  checks need a human moving the device.
- **read_modem**: WiFi association (ssid/bssid/signal −49 dBm),
  `cellular_type:IWLAN`, RSRP −113 (Shizuku live), first-hop 15.5 ms. ✓
- **read_gps**: real cached fix, accuracy 34.5 m, `geofence:null`
  (config empty). ✓

Two fixes from this gate (commit `5a092ad`):
1. Proximity discovery was selecting the "Touch Proximity Sensor" (a
   touchscreen palm-rejection virtual sensor that doesn't answer `-n 1`) →
   READ_ERROR. Added a per-role exclusion so proximity skips "touch"; it now
   resolves to a physical proximity sensor and reads cleanly. Discovery also
   now persists the full `termux-sensor -l` list under sensors.json
   `_available`.
2. read_modem returned `cellular_type:"18"` — this Termux build reports
   `network_type` as the raw Android `TelephonyManager.NETWORK_TYPE_*`
   integer. Added the numeric→label map (18→IWLAN, 13→LTE, 20→5G_NR, …).

## Deviations from the phase-4 prompt (flagging, not hiding)

- **Classifier is pure-Python, not sklearn.** numpy/sklearn wheels bundle
  glibc BLAS that fails bionic dlopen (same lesson as soundfile in Phase
  2); a stdlib rule set is dlopen-safe and unit-testable offline.
- **Still/moving variance gate is 0.04, not the spec's ~0.15.** A literal
  0.15 mislabels walking as on_desk: a horizontal 2 Hz sway peaks at 4 Hz
  in the accel *magnitude* (squaring doubles frequency) and its measured
  variance (~0.10) sits under 0.15. 0.04 sits in the empirical gap
  (desk ~3e-4 ≪ 0.04 ≪ walking ~0.10); periodicity separates the two.
  Walking band widened to 0.8–6 Hz for the same 2f reason (documented).
- **in_pocket confidence capped ≤ 0.6** — genuinely weak from IMU alone
  without proximity/light (spec acknowledges this).
- **cellular_signal_rsrp degrades to null, no hard SHIZUKU_NOT_RUNNING.**
  RSRP needs a hidden API (rish dumpsys); rather than fail the whole read
  when Shizuku is down, rsrp is best-effort and null. first_hop_latency_ms
  is likewise best-effort (gateway via `ip route get`, else 1.1.1.1).
- **geofences.json ships empty** (no fabricated home/work coordinates), so
  `read_gps` returns `geofence: null` until the operator fills it. Runtime
  override at `~/.config/phone-agent/geofences.json` is honored over the
  packaged default.
- **`termux-sensor -c` cleanup** used in a `finally` (not in the spec);
  best-effort and swallowed, cannot break a read.
- **IMU sample pairing:** each accel reading is paired with the most recent
  gyro reading, tolerating both combined and interleaved termux-sensor
  output; timestamps synthesized from the interval (classifier needs only
  relative dt).

## Operator gate items (phone-side)

DONE this session: Termux:API Sensors + Location permissions granted;
deployed + rediscovered; 5/5 live sweep green (above). Remaining items all
need a human physically handling the device:

1. **IMU orientation checks** (I can't move the phone): lay it flat on a
   desk → expect `on_desk` > 0.9; walk with it → expect `walking`. The
   at-rest read already returns `stationary` correctly.
2. **Proximity physical check**: cover the top of the phone → expect
   `is_covered:true`. Discovery currently resolves proximity to "Palm
   Proximity Sensor version 2" (it answers single reads; the physical
   "STK33F15 Proximity …Strm…" variant and the "Touch Proximity" virtual
   sensor were skipped). If the palm sensor doesn't track sustained
   coverage the way you want, the full sensor list is in sensors.json
   `_available` for a re-pick.
3. **Geofences**: fill `~/.config/phone-agent/geofences.json` (or the
   packaged `config/geofences.json`) with `{ "home": {lat,lon,radius_m}, … }`
   to get non-null `geofence` from read_gps.

Laptop side: please run `scripts/verify.sh http://100.101.229.9:8462` over
the tailnet (expect 5/5 @ 17 tools) and sign off per the phase-merge ritual.
Server is already live at `5a092ad`.

## Note on the still-open Phase 3 gate

Phase 3 sign-off + its operator gate (watchdog-install, battery
Unrestricted) are still open per `20260718-phase3-delivery.md`. Phase 4
depends only on the Phase 0 skeleton (no NPU/capture dependency), so it was
built in parallel and does not block on Phase 3 closure.
