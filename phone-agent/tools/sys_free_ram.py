"""phone.system.free_ram — stop non-critical background apps to free RAM."""

from pathlib import Path

from tools.sys_common import SystemToolError, rish_call

KILL_CANDIDATES = [
    "com.android.chrome",
    "com.instagram.android",
    "com.facebook.katana",
    "com.twitter.android",
    "com.spotify.music",
    "com.google.android.youtube",
    "com.snapchat.android",
]

# Only for aggressiveness="aggressive". Messengers are deliberately absent
# alongside the obvious system packages: force-stop suspends an app's
# notification delivery until it is reopened, so stopping WhatsApp/Telegram
# to reclaim a few hundred MB silently costs the operator real messages.
ADDITIONAL_KILL_CANDIDATES = [
    "com.netflix.mediaclient",
    "com.reddit.frontpage",
    "com.zhiliaoapp.musically",
    "com.amazon.mShop.android.shopping",
]

# Loop-exit heuristic only — never reported as freed_mb.
ASSUMED_MB_PER_APP = 100


def _read_mem_available_kb() -> int:
    """MemAvailable in kB. /proc/meminfo is world-readable — no rish."""
    try:
        text = Path("/proc/meminfo").read_text()
    except OSError as e:
        raise SystemToolError("MEMINFO_UNAVAILABLE", f"cannot read meminfo: {e}")
    for line in text.splitlines():
        if line.startswith("MemAvailable:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1])
    raise SystemToolError("MEMINFO_UNAVAILABLE", "MemAvailable field not found")


def register(mcp):
    @mcp.tool(name="phone.system.free_ram")
    async def free_ram(target_free_mb: int, aggressiveness: str = "normal") -> dict:
        """Stop non-critical background apps (am force-stop via rish) until
        MemAvailable reaches target_free_mb. aggressiveness is "normal"
        (user-facing apps) or "aggressive" (a wider list). Returns freed_mb
        — the real /proc/meminfo delta, not an estimate — plus available_mb
        and killed_packages. Advisory: Android's low-memory killer may
        reclaim differently. Errors: MEMINFO_UNAVAILABLE,
        SHIZUKU_NOT_RUNNING, NO_APPS_TO_KILL, INSUFFICIENT_TARGET."""
        killed: list[str] = []
        initial_kb = 0
        try:
            initial_kb = _read_mem_available_kb()
            # Target already met: answer without touching rish, so the tool
            # still works with Shizuku stopped.
            if initial_kb // 1024 >= target_free_mb:
                return {"freed_mb": 0, "available_mb": initial_kb // 1024,
                        "killed_packages": []}

            candidates = list(KILL_CANDIDATES)
            if aggressiveness == "aggressive":
                candidates += ADDITIONAL_KILL_CANDIDATES

            estimated_mb = 0
            for pkg in candidates:
                res = await rish_call(f"pidof -s {pkg}")
                if res["exit_code"] != 0 or not res["stdout"].strip():
                    continue
                # force-stop, not `am kill`: it lets the app save state.
                await rish_call(f"am force-stop {pkg}")
                killed.append(pkg)
                estimated_mb += ASSUMED_MB_PER_APP
                if (initial_kb // 1024) + estimated_mb >= target_free_mb:
                    break

            if not killed:
                raise SystemToolError("NO_APPS_TO_KILL",
                                      "no candidate app was running")

            final_kb = _read_mem_available_kb()
            result = {
                "freed_mb": max(0, (final_kb - initial_kb) // 1024),
                "available_mb": final_kb // 1024,
                "killed_packages": killed,
            }
            if result["available_mb"] < target_free_mb:
                raise SystemToolError(
                    "INSUFFICIENT_TARGET",
                    f"candidates exhausted at {result['available_mb']} MB "
                    f"available (target {target_free_mb} MB)")
            return result
        except SystemToolError as e:
            # Report what was stopped even on the error paths — the caller
            # cannot un-stop these apps and needs to know they were hit.
            out = {"error": e.code, "message": e.message,
                   "killed_packages": killed}
            if killed:
                try:
                    final_kb = _read_mem_available_kb()
                    out["available_mb"] = final_kb // 1024
                    out["freed_mb"] = max(0, (final_kb - initial_kb) // 1024)
                except SystemToolError:
                    pass
            return out
