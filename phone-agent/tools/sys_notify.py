"""phone.system.notify — Android notification via termux-notification."""

import itertools
import shlex

from tools.sys_common import SystemToolError, run_shell

# termux-notification prints nothing, so the id is ours to generate and pass
# explicitly (D10). It restarts at 1 with the service: an id reused after a
# bounce replaces whatever notification still holds it in the shade.
_notify_ids = itertools.count(1)


def register(mcp):
    @mcp.tool(name="phone.system.notify")
    async def notify(title: str, body: str, priority: str = "normal",
                     click_action: str | None = None) -> dict:
        """Post a notification to the status bar. priority "high" makes it a
        heads-up with sound, "low" is silent and minimized, "normal" goes
        quietly to the shade; click_action is a shell command run on tap.
        Returns the notification_id. Honours Do Not Disturb — under total
        silence even high priority may be suppressed. Errors: TITLE_EMPTY,
        NOTIFY_FAILED, COMMAND_NOT_FOUND."""
        if not title.strip():
            return {"error": "TITLE_EMPTY",
                    "message": "Android requires a non-empty title"}

        nid = next(_notify_ids)
        cmd = (f"termux-notification --id {nid} "
               f"--title {shlex.quote(title)} --content {shlex.quote(body)}")
        if priority in ("high", "low"):
            cmd += f" --priority {priority}"
        if click_action:
            cmd += f" --action {shlex.quote(click_action)}"

        try:
            res = await run_shell(cmd)
            if res["exit_code"] != 0:
                detail = (res["stderr"].strip() or res["stdout"].strip()
                          or f"termux-notification exited {res['exit_code']}")
                raise SystemToolError("NOTIFY_FAILED", detail[:200])
            return {"notification_id": nid}
        except SystemToolError as e:
            return {"error": e.code, "message": e.message}
