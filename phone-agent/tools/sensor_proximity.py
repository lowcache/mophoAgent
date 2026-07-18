"""phone.sensor.read_proximity — proximity sensor (distance + covered flag)."""

from tools.sensor_common import SensorError, get_sensor_name, read_sensors, values_for

# Most phone proximity sensors are effectively binary: ~0 cm when covered,
# ~5 cm when clear. Treat anything under 2 cm as covered.
COVERED_THRESHOLD_CM = 2.0


def register(mcp):
    @mcp.tool(name="phone.sensor.read_proximity")
    async def read_proximity() -> dict:
        """Read the proximity sensor once (termux-sensor). Returns
        distance_cm and is_covered (distance_cm < 2.0). Most sensors report
        a binary 0/5 cm rather than a true distance. No input. Errors:
        SENSOR_NOT_AVAILABLE, PERMISSION_DENIED, READ_ERROR."""
        try:
            name = await get_sensor_name("proximity")
            readings = await read_sensors([name], 1, 200)
            vals = values_for(readings[0], name) if readings else None
            if not vals:
                raise SensorError("READ_ERROR", "proximity sensor returned no value")
            distance_cm = round(float(vals[0]), 1)
            return {"distance_cm": distance_cm,
                    "is_covered": distance_cm < COVERED_THRESHOLD_CM}
        except SensorError as e:
            return {"error": e.code, "message": e.message}
