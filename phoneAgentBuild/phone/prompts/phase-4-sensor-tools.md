# Phase 4: Sensor Tools

**Target Agent:** Claude Code (phone, Termux)
**Commit message:** `feat(phone-mcp): sensor tools — IMU, modem, GPS, light, proximity`

---

## What You Are Building

Five MCP tools that read the phone's hardware sensors. These enable Proximity-Aware Mode and Network Context Engine (Phase 8). The IMU includes an on-device activity classifier (on_desk, walking, in_pocket, etc.) that runs a lightweight model on the NPU or CPU.

---

## Prerequisites

Phase 0 built. This phase has no dependency on NPU or capture — it only needs the MCP server skeleton.

---

## File Structure

```
~/phone-agent/
├── tools/
│   ├── sensor_imu.py               # NEW: phone.sensor.read_imu
│   ├── sensor_modem.py             # NEW: phone.sensor.read_modem
│   ├── sensor_gps.py               # NEW: phone.sensor.read_gps
│   ├── sensor_light.py             # NEW: phone.sensor.read_light
│   ├── sensor_proximity.py         # NEW: phone.sensor.read_proximity
├── sensors/
│   ├── __init__.py
│   ├── activity.py                 # NEW: IMU activity classifier
│   ├── geofence.py                 # NEW: geofence checker
└── config/
    ├── geofences.json              # NEW: user-defined geofences
```

---

## Implementation Spec

### sensors/activity.py — IMU Activity Classifier

A lightweight classifier that takes IMU samples and returns an activity label.

**Algorithm:** Simple statistical features on a 1-second window of accelerometer data:
- Mean acceleration magnitude — distinguishes stationary (≈9.8 m/s²) from moving
- Variance of acceleration — low variance = stationary/on_desk, high variance = walking/running
- Peak frequency (via FFT of first 50 samples) — walking ≈2Hz, typing vibration ≈5-10Hz
- Orientation (gravity vector direction) — phone flat on desk vs in pocket vs in hand

**Feature vector (6 float values):**
1. Mean acceleration magnitude
2. Variance of acceleration magnitude
3. Peak frequency in 0.5-10Hz range
4. Gravity angle from vertical (degrees)
5. Zero-crossing rate (count of sign changes in the last 50 samples)
6. Energy ratio (high-frequency / low-frequency energy, crossover at 3Hz)

**Classifier:** A small decision tree or logistic regression (~10KB, runs on CPU in <5ms):

```python
class ActivityClassifier:
    def __init__(self):
        # Lightweight model — could be a sklearn LogisticRegression or a simple rule set
        pass

    def classify(self, samples: list[dict]) -> dict:
        """
        Input: list of { accel: [x,y,z], gyro: [x,y,z], timestamp }
        Output: { "inference": str, "confidence": float }
        
        Inference values:
        - "on_desk" — stationary, flat orientation, low variance
        - "in_hand" — stationary or slow moving, upright orientation
        - "in_pocket" — dark sensor (combined with proximity), walking variance
        - "walking" — periodic acceleration at ~2Hz
        - "stationary" — still but not on desk (holding still, sitting)
        - "unknown" — can't determine
        """
```

### tools/sensor_imu.py — `phone.sensor.read_imu`

Read accelerometer + gyroscope and classify the activity.

**Input:**
```json
{
  "sample_count": 50,
  "sample_interval_ms": 20
}
```

**Output:**
```json
{
  "samples": [
    { "accel": [0.1, 9.8, 0.2], "gyro": [0.01, 0.00, -0.01] }
  ],
  "inference": "on_desk",
  "inference_confidence": 0.95
}
```

**Implementation:**
- Use Android's `SensorManager` via `termux-sensor -s "{accel_name},{gyro_name}" -n {sample_count} -d {sample_interval_ms}` (`-s` takes comma-separated sensor names; `-d` is delay in ms)
- Sensor names are device-specific (e.g. `lsm6dso Accelerometer`). Discover them once with `termux-sensor -l` at setup and cache the mapping in `~/.config/phone-agent/sensors.json`
- Parse the JSON output
- Note: `in_pocket` inference is weak from IMU alone; the classifier may consult `read_light`/`read_proximity` as a documented heuristic
- Run `ActivityClassifier.classify()` on the samples
- Return the samples + inference result

**Error states:**
- `SENSOR_NOT_AVAILABLE` — phone doesn't have the required sensor
- `PERMISSION_DENIED` — sensor permission not granted

### tools/sensor_modem.py — `phone.sensor.read_modem`

Read network state — WiFi and cellular.

**Input:**
```json
{
  "fields": ["bssid", "signal_dbm", "network_type"]
}
```

**Output:**
```json
{
  "bssid": "ab:cd:ef:12:34:56",
  "ssid": "HomeWiFi",
  "signal_dbm": -45,
  "network_type": "WiFi",
  "cellular_type": "5G_NR",
  "cellular_signal_rsrp": -95,
  "is_roaming": false,
  "first_hop_latency_ms": 3.2
}
```

**Implementation approaches (try in order):**

1. **Termux:API** — `termux-wifi-connectioninfo` and `termux-telephony-deviceinfo`:
   ```bash
   termux-wifi-connectioninfo   # Current association: BSSID, SSID, rssi, link speed
   termux-telephony-deviceinfo  # Cellular: network type, signal, roaming
   ```
   (`termux-wifi-scaninfo` lists *neighboring* networks — only useful for scans, not the current connection.)

2. **Shizuku rish** for hidden APIs (fields Termux:API can't reach):
   ```bash
   rish -c 'dumpsys wifi | grep "mNetworkInfo"'
   rish -c 'dumpsys telephony.registry | grep "mSignalStrength"'
   ```
   Parse the dumpsys output.

3. **Ping-based latency** — `ping -c 1 -W 1 {gateway_ip}` for `first_hop_latency_ms` (fall back to `1.1.1.1` if the gateway is unknown — not ideal but works).

**Notes:**
- Fields like `bssid` and `ssid` are only available when connected to WiFi. When on cellular only, set `network_type: "5G_NR"` (or LTE, etc.) and leave `bssid`/`ssid` null.
- `cellular_type` comes from `termux-telephony-deviceinfo`'s `network_operator` field.

**Error states:**
- `NO_CONNECTIVITY` — no WiFi or cellular
- `SHIZUKU_NOT_RUNNING` — for dumpsys-based fields that need rish

### tools/sensor_gps.py — `phone.sensor.read_gps`

Single-shot GPS location reading.

**Input:**
```json
{
  "timeout_sec": 5
}
```

**Output:**
```json
{
  "lat": 41.8827,
  "lon": -87.6233,
  "accuracy_m": 15,
  "geofence": "home"
}
```

**Implementation:**
```bash
termux-location -r last          # Cached last-known fix (low power); JSON with lat, lon, accuracy
# termux-location -r once -p gps # Fresh GPS fix (slower, more battery) — use when accuracy matters
```

Parse the output. Check against `config/geofences.json` for named geofences.

**Geofence definitions** (`config/geofences.json`):
```json
{
  "home": { "lat": 41.88, "lon": -87.62, "radius_m": 100 },
  "work": { "lat": 41.89, "lon": -87.63, "radius_m": 200 }
}
```

The `geofence` field in the output is the name of the matching geofence, or `null` if no match.

**Error states:**
- `GPS_TIMEOUT` — no fix within `timeout_sec` (indoor, no line of sight)
- `GPS_DISABLED` — location services are off

### tools/sensor_light.py — `phone.sensor.read_light`

Read ambient light sensor.

**Input:** None (empty arguments)

**Output:**
```json
{
  "lux": 320,
  "label": "indoor_bright"
}
```

**Implementation:**
```bash
termux-sensor -s "Light" -n 1
```

**Lux label mapping:**
| Range (lux) | Label |
|---|---|
| 0 | pitch_black |
| 1-50 | dim |
| 51-500 | indoor_bright |
| 501-20000 | outdoor_shade |
| >20000 | direct_sunlight |

**Error states:**
- `SENSOR_NOT_AVAILABLE` — no light sensor on device

### tools/sensor_proximity.py — `phone.sensor.read_proximity`

Read the proximity sensor.

**Input:** None (empty arguments)

**Output:**
```json
{
  "distance_cm": 0.5,
  "is_covered": true
}
```

**Implementation:**
```bash
termux-sensor -s "Proximity" -n 1
```

Proximity sensors typically return 0.0cm (covered) or 5.0cm (not covered). Map to `is_covered: distance_cm < 2.0`.

**Error states:**
- `SENSOR_NOT_AVAILABLE`
- `READ_ERROR` — sensor returned unexpected value

---

## Test Procedure

1. Test IMU: Place phone on desk. Call `phone.sensor.read_imu`. Verify inference is `on_desk` with >0.9 confidence.
2. Test IMU: Pick up phone and walk. Call again. Verify inference is `walking`.
3. Test modem: Verify WiFi SSID and signal strength are correct.
4. Test GPS: Run outdoors. Verify lat/lon match your real location.
5. Test light: Place phone under bright light, then cover sensor. Verify labels change.
6. Test proximity: Cover the top of the phone. Verify `is_covered: true`.

---

## Acceptance Criteria

- [ ] `phone.sensor.read_imu` returns correct activity inference for on_desk, walking, in_pocket
- [ ] Activity inference completes in < 50ms (CPU, no NPU)
- [ ] `phone.sensor.read_modem` returns WiFi SSID and signal when connected
- [ ] `phone.sensor.read_modem` returns cellular type when on mobile data
- [ ] `phone.sensor.read_gps` returns location within accuracy_m of true position
- [ ] `phone.sensor.read_gps` returns named geofence when inside a defined zone
- [ ] `phone.sensor.read_light` returns lux value and correct label for 5 test levels
- [ ] `phone.sensor.read_proximity` returns correct `is_covered` state
- [ ] All 5 sensors return proper error codes when unavailable

---

## Guardrails

- **No NPU usage.** All sensor processing is CPU. IMU classifier is a <10KB linear model or decision tree, not a neural network.
- **Single shot, not streaming.** Each tool call queries the sensor once and returns. Continuous monitoring (e.g., watch IMU every 5 seconds for proximity lock) belongs in Phase 7 (Scheduler) or Phase 8 (Laptop Agent polling).
- **GPS is low-power.** `termux-location -r last` uses the last known location, not a fresh GPS lock, to minimize battery impact. A fresh fix requires `termux-location -r once -p gps`.
- **All sensors must handle "not available" gracefully.** Different Android phones have different sensor suites. S26 Ultra has all of these, but the code should degrade gracefully if one is missing.

---

## Git Commit

```bash
git add -A
git commit -m "feat(phone-mcp): sensor tools — IMU, modem, GPS, light, proximity"
git tag phone-mcp-phase-4
git push origin phone
```

Rollback: `git revert HEAD`. Sensor tools revert. All other functionality unaffected.
