"""phone.sensor.read_light — ambient light sensor (lux + coarse label)."""

from tools.sensor_common import SensorError, get_sensor_name, read_sensors, values_for


def _label(lux: float) -> str:
    if lux < 1:
        return "pitch_black"
    if lux <= 50:
        return "dim"
    if lux <= 500:
        return "indoor_bright"
    if lux <= 20000:
        return "outdoor_shade"
    return "direct_sunlight"


def register(mcp):
    @mcp.tool(name="phone.sensor.read_light")
    async def read_light() -> dict:
        """Read the ambient light sensor once (termux-sensor). Returns lux
        and a coarse label (pitch_black, dim, indoor_bright, outdoor_shade,
        direct_sunlight). No input. Errors: SENSOR_NOT_AVAILABLE,
        PERMISSION_DENIED, READ_ERROR."""
        try:
            name = await get_sensor_name("light")
            readings = await read_sensors([name], 1, 200)
            vals = values_for(readings[0], name) if readings else None
            if not vals:
                raise SensorError("READ_ERROR", "light sensor returned no value")
            lux = round(float(vals[0]), 1)
            return {"lux": lux, "label": _label(lux)}
        except SensorError as e:
            return {"error": e.code, "message": e.message}
