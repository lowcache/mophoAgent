"""IMU activity classifier — heuristic rule set, not a trained model.

Runs under native Termux Python (D2) with **stdlib math only**: numpy wheels
that bundle glibc BLAS fail bionic dlopen on-device (see tools/capture_audio.py
for the same soundfile lesson), and the sample counts here (<=50) are tiny
enough that a pure-Python DFT is trivially fast (<50ms for 50 samples).

The classifier is a transparent decision tree over six hand-computed features,
labelled below. It is a heuristic — the thresholds were tuned against synthetic
IMU signals (see tests/test_activity.py), not learned from data.

Public API:
    classify(samples) -> {"inference": str, "confidence": float}
    ActivityClassifier().classify(samples) -> same

Label vocabulary: on_desk, in_hand, in_pocket, walking, stationary, unknown.
"""

import math

# --- tuning constants -------------------------------------------------------
# Below this fewer-samples floor the spectrum/variance estimates are too noisy
# to trust, so we bail to "unknown" rather than guess.
MIN_SAMPLES = 8

# Variance (m/s^2)^2 of accel magnitude that separates "still" from "moving".
# Chosen to sit in the wide empirical gap between desk sensor noise (~1e-3) and
# a walking oscillation (~1e-1); a single gate keeps desk vs walking robust
# even though both can present a near-vertical mean gravity vector.
STILL_VAR = 0.04

# A phone flat on a desk reads gravity along +z, so its mean-accel vector is
# within a few degrees of the device z-axis. Anything past this is "tilted".
FLAT_ANGLE = 15.0

# Beyond this the device is closer to on-edge/upright than lying flat; used to
# gate the (IMU-weak) in_pocket guess.
STEEP_ANGLE = 45.0

# Locomotion band for the magnitude spectrum. Note it is intentionally wide and
# reaches past a literal ~2 Hz step cadence: a purely *horizontal* acceleration
# of frequency f shows up in the accel *magnitude* at 2f (magnitude squares the
# component, and sin^2 has twice the frequency), so a 2 Hz sway peaks near 4 Hz
# in this series. Real walking also injects vertical bounce near the step rate,
# so genuine gait energy lands somewhere in [~1, ~5] Hz.
WALK_LO_HZ = 0.8
WALK_HI_HZ = 6.0

# Peak-frequency search band for feature 3 (spec-mandated).
PEAK_LO_HZ = 0.5
PEAK_HI_HZ = 10.0

# LF/HF split (Hz) for the energy-ratio feature.
HF_SPLIT_HZ = 3.0

# Gyro magnitude (rad/s) above which we read a "tremor" — a held device is
# never perfectly still, a set-down one is.
TREMOR_GYRO = 0.03

DEFAULT_RATE_HZ = 50.0
_EPS = 1e-9


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _variance(xs: list[float]) -> float:
    if not xs:
        return 0.0
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / len(xs)


def _sample_rate(samples: list[dict]) -> float:
    """Median-dt estimate of the sampling rate, in Hz.

    Median (not mean) so a single dropped/duplicated timestamp does not skew
    the rate. Falls back to DEFAULT_RATE_HZ when timestamps are absent,
    identical, or otherwise degenerate."""
    ts = [s.get("timestamp") for s in samples]
    dts = [ts[i + 1] - ts[i]
           for i in range(len(ts) - 1)
           if ts[i] is not None and ts[i + 1] is not None]
    dts = sorted(d for d in dts if d > 0)
    if not dts:
        return DEFAULT_RATE_HZ
    med = dts[len(dts) // 2]
    return 1.0 / med if med > 0 else DEFAULT_RATE_HZ


def _dft_power(x: list[float]) -> list[float]:
    """Pure-Python real DFT power spectrum for bins k = 0..n//2.

    power[k] = real^2 + imag^2 where
        real =  sum_i x[i] cos(2*pi*k*i/n)
        imag = -sum_i x[i] sin(2*pi*k*i/n)
    n <= 50 so the O(n^2) cost (~650 bin*sample ops) is negligible."""
    n = len(x)
    powers = []
    for k in range(n // 2 + 1):
        real = 0.0
        imag = 0.0
        for i in range(n):
            ang = 2.0 * math.pi * k * i / n
            real += x[i] * math.cos(ang)
            imag -= x[i] * math.sin(ang)
        powers.append(real * real + imag * imag)
    return powers


def _features(samples: list[dict], sample_rate: float | None = None) -> dict:
    """Extract the six-element feature vector used by the decision tree.

    sample_rate is optional; when omitted it is derived from timestamps so the
    public classify() works from timestamps alone."""
    if sample_rate is None:
        sample_rate = _sample_rate(samples)

    accel = [s["accel"] for s in samples]
    gyro = [s.get("gyro", [0.0, 0.0, 0.0]) for s in samples]

    # Feature 1 & 2: mean and variance of accel magnitude.
    mags = [math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2) for a in accel]
    mean_mag = _mean(mags)
    var_mag = _variance(mags)

    # DFT of the mean-detrended magnitude series (first <=50 samples) drives
    # features 3 and 6. Detrending kills the DC/gravity bin so the spectrum is
    # purely about motion.
    series = mags[:50]
    detr = [m - _mean(series) for m in series]
    n = len(series)
    rate = sample_rate
    powers = _dft_power(detr)

    # Feature 3: peak frequency (Hz) of the max-power bin inside [0.5, 10] Hz;
    # 0.0 if the band is empty (e.g. n too small to resolve it).
    peak_freq = 0.0
    peak_power = 0.0
    for k, p in enumerate(powers):
        f = k * rate / n if n else 0.0
        if PEAK_LO_HZ <= f <= PEAK_HI_HZ and p > peak_power:
            peak_power = p
            peak_freq = f

    # Feature 6: high-freq (>3 Hz) energy over low-freq (0 < f <= 3 Hz) energy.
    lf_energy = 0.0
    hf_energy = 0.0
    for k, p in enumerate(powers):
        f = k * rate / n if n else 0.0
        if f <= 0.0:
            continue  # skip DC (already ~0 after detrend)
        if f <= HF_SPLIT_HZ:
            lf_energy += p
        else:
            hf_energy += p
    energy_ratio = hf_energy / (lf_energy + _EPS)

    # Feature 4: angle (deg) between the mean accel (gravity) vector and the
    # device z-axis [0,0,1]. Flat-on-desk ~0 deg, upright ~90 deg.
    mx = _mean([a[0] for a in accel])
    my = _mean([a[1] for a in accel])
    mz = _mean([a[2] for a in accel])
    norm = math.sqrt(mx * mx + my * my + mz * mz)
    if norm < _EPS:
        gravity_angle = 90.0  # no gravity direction to speak of; treat as tilted
    else:
        gravity_angle = math.degrees(math.acos(_clamp(mz / norm, -1.0, 1.0)))

    # Feature 5: zero-crossing rate of the detrended magnitude (sign flips).
    zero_crossings = 0
    for i in range(1, len(detr)):
        if (detr[i - 1] < 0) != (detr[i] < 0):
            zero_crossings += 1

    # Tremor: mean gyro magnitude, distinguishes held (tiny tremor) from
    # set-down (essentially zero) when otherwise still.
    gyro_mag = _mean([math.sqrt(g[0] ** 2 + g[1] ** 2 + g[2] ** 2) for g in gyro])

    return {
        "n": len(samples),
        "rate": rate,
        "mean_mag": mean_mag,      # feature 1
        "var_mag": var_mag,        # feature 2
        "peak_freq": peak_freq,    # feature 3
        "peak_power": peak_power,
        "gravity_angle": gravity_angle,  # feature 4
        "zero_crossings": zero_crossings,  # feature 5
        "energy_ratio": energy_ratio,      # feature 6
        "gyro_mag": gyro_mag,
    }


def _decide(f: dict) -> dict:
    """Rule-based decision tree over the feature vector.

    Confidence is derived from the margin between the winning branch's
    discriminating feature(s) and its threshold, clamped to [0.3, 0.98] — never
    a bare 1.0, since this is a heuristic."""
    var = f["var_mag"]
    angle = f["gravity_angle"]
    peak = f["peak_freq"]

    if var < STILL_VAR:
        # --- essentially not moving -------------------------------------
        if angle < FLAT_ANGLE:
            # Flat and still => lying on a desk. Confidence grows as both the
            # tilt and the variance sit further inside their thresholds.
            m = min((FLAT_ANGLE - angle) / FLAT_ANGLE,
                    (STILL_VAR - var) / STILL_VAR)
            return {"inference": "on_desk",
                    "confidence": _clamp(0.6 + 0.4 * m, 0.3, 0.98)}
        # Still but tilted: set down on edge, or held very still.
        tilt_m = min(1.0, angle / 90.0)
        still_m = (STILL_VAR - var) / STILL_VAR
        conf = _clamp(0.4 + 0.4 * min(tilt_m, still_m), 0.3, 0.98)
        if f["gyro_mag"] > TREMOR_GYRO:
            return {"inference": "in_hand", "confidence": conf}
        return {"inference": "stationary", "confidence": conf}

    # --- moving ---------------------------------------------------------
    if WALK_LO_HZ <= peak <= WALK_HI_HZ and f["peak_power"] > 0.0:
        # Elevated variance with a clear in-band spectral peak => walking.
        # Confidence from how far the variance clears the movement gate and how
        # centred the peak is in the locomotion band.
        var_m = min(1.0, (var - STILL_VAR) / (STILL_VAR * 2.0))
        centre = (WALK_LO_HZ + WALK_HI_HZ) / 2.0
        peak_m = 1.0 - abs(peak - centre) / (WALK_HI_HZ - centre)
        conf = _clamp(0.55 + 0.4 * min(var_m, max(0.0, peak_m)), 0.3, 0.98)
        return {"inference": "walking", "confidence": conf}

    if angle > STEEP_ANGLE and f["energy_ratio"] > 0.5:
        # Steep tilt + broadband (HF-heavy) energy loosely fits a phone jostling
        # in a pocket. [CONTEXT REQ] in_pocket is genuinely weak to infer from
        # the IMU alone (no proximity/light sensor here), so it is a low-priority
        # branch with capped confidence.
        return {"inference": "in_pocket",
                "confidence": _clamp(0.3 + 0.2 * min(1.0, f["energy_ratio"]),
                                     0.3, 0.6)}

    # Moving but without clean gait periodicity: handled/fidgeting in the hand.
    return {"inference": "in_hand", "confidence": 0.5}


class ActivityClassifier:
    """Class form of the classifier (the spec references one). Stateless — it
    just wraps the module-level feature extraction and decision tree."""

    def classify(self, samples: list[dict]) -> dict:
        return classify(samples)


def classify(samples: list[dict]) -> dict:
    """Classify a short IMU window into an activity label + confidence.

    Input: list of {"accel": [x,y,z], "gyro": [x,y,z], "timestamp": seconds}.
    Output: {"inference": str, "confidence": float in [0.0, 1.0]}."""
    if not samples or len(samples) < MIN_SAMPLES:
        return {"inference": "unknown", "confidence": 0.3}
    return _decide(_features(samples))
