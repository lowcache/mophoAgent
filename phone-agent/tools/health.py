from datetime import datetime, timezone
import time
from config.settings import SERVER_START_MONOTONIC

def register(mcp):
    @mcp.tool(name='phone.system.ping')
    def ping() -> dict:
        """Liveness probe. Returns server status, current UTC timestamp, and
        seconds since the MCP server started. No input; use to confirm the
        phone MCP endpoint is reachable and responsive."""
        uptime_sec = int(time.monotonic() - SERVER_START_MONOTONIC)
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        return {
            "status": "ok",
            "timestamp": timestamp,
            "uptime_sec": uptime_sec
        }

    @mcp.tool(name='phone.system.state')
    def state() -> dict:
        """Snapshot of phone health for scheduling decisions: battery percent,
        charging flag, thermal state, available RAM (MB), MCP server uptime,
        active tool names, and pending queue depth. No input. Phase 0 returns
        static placeholders; real sensor wiring lands in later phases."""
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
