"""phone.sensor.read_imu — accelerometer + gyroscope sample burst with an
on-device activity inference. CPU only (D5); no NPU (Phase 4 guardrail)."""

from sensors.activity import classify
from tools.sensor_common import (
    SensorError, get_sensor_name, read_sensors, values_for,
)


def register(mcp):
    @mcp.tool(name="phone.sensor.read_imu")
    async def read_imu(sample_count: int = 50, sample_interval_ms: int = 20) -> dict:
        """Read a burst of accelerometer + gyroscope samples
        (termux-sensor) and classify the phone's activity on-device
        (on_desk, in_hand, in_pocket, walking, stationary, unknown) with a
        lightweight CPU rule set — no NPU. Returns the raw samples plus
        inference + inference_confidence. Errors: SENSOR_NOT_AVAILABLE,
        PERMISSION_DENIED, READ_ERROR."""
        try:
            accel = await get_sensor_name("accelerometer")
            gyro = await get_sensor_name("gyroscope")
            readings = await read_sensors([accel, gyro], sample_count,
                                          sample_interval_ms)

            # termux-sensor may emit accel+gyro in one reading or interleave
            # them; pair each accelerometer sample with the most recent gyro
            # reading (zeros until the first arrives) and synthesise
            # timestamps from the requested interval — the classifier only
            # needs relative dt for its FFT.
            dt = sample_interval_ms / 1000.0
            samples = []
            last_gyro = [0.0, 0.0, 0.0]
            for r in readings:
                g = values_for(r, gyro)
                if g:
                    last_gyro = [float(v) for v in g[:3]]
                a = values_for(r, accel)
                if a:
                    samples.append({
                        "accel": [float(v) for v in a[:3]],
                        "gyro": list(last_gyro),
                        "timestamp": len(samples) * dt,
                    })

            if not samples:
                raise SensorError("READ_ERROR", "no accelerometer readings returned")

            result = classify(samples)
            # Drop the synthetic timestamp from the returned samples to match
            # the tool schema (accel + gyro only).
            return {
                "samples": [{"accel": s["accel"], "gyro": s["gyro"]} for s in samples],
                "inference": result["inference"],
                "inference_confidence": round(float(result["confidence"]), 2),
            }
        except SensorError as e:
            return {"error": e.code, "message": e.message}
