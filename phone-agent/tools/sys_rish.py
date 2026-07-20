"""phone.system.rish — run a command at shell uid via Shizuku's rish."""

from tools.sys_common import SystemToolError, rish_call


def register(mcp):
    @mcp.tool(name="phone.system.rish")
    async def rish(command: str, timeout_sec: int = 10) -> dict:
        """Execute `command` through Shizuku's rish shell (ADB/shell-level
        privileges). Returns stdout, stderr, exit_code, execution_time_ms.
        Commands matching ~/.config/phone-agent/rish_blocklist.txt are
        refused. Errors: FORBIDDEN_COMMAND, BLOCKLIST_UNAVAILABLE,
        SHIZUKU_NOT_RUNNING, TIMEOUT, RISH_ERROR."""
        try:
            return await rish_call(command, timeout_sec=timeout_sec)
        except SystemToolError as e:
            return {"error": e.code, "message": e.message}
