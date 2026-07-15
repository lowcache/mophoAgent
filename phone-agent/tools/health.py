from datetime import datetime, timezone
import time
from config.settings import SERVER_START_MONOTONIC

def register(mcp):
    @mcp.tool(name='phone.system.ping')
    def ping() -> dict:
        uptime_sec = int(time.monotonic() - SERVER_START_MONOTONIC)
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        return {
            "status": "ok",
            "timestamp": timestamp,
            "uptime_sec": uptime_sec
        }

    @mcp.tool(name='phone.system.state')
    def state() -> dict:
        uptime_sec = int(time.monotonic() - SERVER_START_MONOTONIC)
        return {
            "battery_pct": 100,
            "charging": True,
            "thermal_state": "cool",
            "available_ram_mb": 4096,
            "mcp_server_uptime_sec": uptime_sec,
            "active_tools": [],
            "pending_queue_depth": 0
        }
