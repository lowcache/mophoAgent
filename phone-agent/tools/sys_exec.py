"""phone.system.termux_exec — run a command in the native Termux shell."""

from tools.sys_common import SystemToolError, run_shell


def register(mcp):
    @mcp.tool(name="phone.system.termux_exec")
    async def termux_exec(command: str, timeout_sec: int = 30,
                          workdir: str = "~") -> dict:
        """Execute `command` in Termux's bash (not Android's /system/bin/sh)
        with `workdir` as cwd; `~` and `$HOME` expand. Returns stdout,
        stderr, exit_code, execution_time_ms. Runs at the unprivileged
        Termux uid, but is screened by the same blocklist as phone.system.rish
        — it inherits the service PATH and can invoke rish itself, so the two
        are not separate privilege tiers. Errors: FORBIDDEN_COMMAND,
        BLOCKLIST_UNAVAILABLE, WORKDIR_NOT_FOUND, TIMEOUT,
        COMMAND_NOT_FOUND."""
        try:
            return await run_shell(command, timeout_sec=timeout_sec,
                                   workdir=workdir)
        except SystemToolError as e:
            return {"error": e.code, "message": e.message}
