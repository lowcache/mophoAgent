# Phase 5: System Tools

**Target Agent:** Claude Code (phone, Termux)
**Commit message:** `feat(phone-mcp): system tools — rish, exec, free_ram, notify`

---

## What You Are Building

Four MCP tools for system-level operations: executing commands via Shizuku rish (with safety filters), running commands in Termux, freeing RAM by killing background apps, and sending system notifications.

---

## Prerequisites

Phase 0 built. Shizuku must be installed and running on the phone (user responsibility, documented in README).

---

## File Structure

```
~/phone-agent/
├── tools/
│   ├── sys_rish.py                 # NEW: phone.system.rish
│   ├── sys_exec.py                 # NEW: phone.system.termux_exec
│   ├── sys_free_ram.py             # NEW: phone.system.free_ram
│   ├── sys_notify.py               # NEW: phone.system.notify
├── config/
│   ├── rish_blocklist.txt          # NEW: blocked command patterns (installed to ~/.config/phone-agent/)
```

---

## Implementation Spec

### config/rish_blocklist.txt

Command patterns that `phone.system.rish` will refuse to execute. **One regex per line** (matched with `re.search`, case-sensitive), comments with `#`. Plain fnmatch/exact-string matching is too weak — `"rm -rf /"` as an exact string never matches `"rm -rf / --no-preserve-root"`.

```
# File system destruction
^rm\s+(-[a-zA-Z-]+\s+)*/(\s|$|\*)

# Partition manipulation
^mkfs\.
^fdisk
^dd\s+.*if=/dev/(zero|u?random)

# System modification
mount\s+-o\s+remount,rw\s+/

# Factory reset
wipe_data
recovery\s+--wipe_data
^fastboot

# Bootloader
flash_image
unlock_bootloader
```

**Note:** `rish_blocklist.txt` is a safety net, not a security boundary. A determined user can edit it or bypass it. It prevents accidental destructive commands, not malicious ones.

### tools/sys_rish.py — `phone.system.rish`

Execute a command through Shizuku's rish shell (ADB/shell-level privileges).

**Input:**
```json
{
  "command": "am force-stop com.android.chrome",
  "timeout_sec": 10
}
```

**Output:**
```json
{
  "stdout": "",
  "stderr": "",
  "exit_code": 0,
  "execution_time_ms": 234
}
```

**Implementation:**

```python
import re, subprocess, time

BLOCKLIST = load_blocklist_regexes("~/.config/phone-agent/rish_blocklist.txt")

async def rish_call(command: str, timeout_sec: int = 10) -> dict:
    # 1. Safety check — regex search, case-sensitive, against the raw command
    for pattern in BLOCKLIST:
        if re.search(pattern, command):
            raise ToolError("FORBIDDEN_COMMAND", f"Command matches blocklist pattern: {pattern.pattern}")

    # 2. Execute via rish (accepts commands on stdin: echo "cmd" | rish)
    start = time.time()
    proc = subprocess.run(
        ["rish"],
        input=command.encode(),
        capture_output=True,
        timeout=timeout_sec
    )
    elapsed = int((time.time() - start) * 1000)

    return {
        "stdout": proc.stdout.decode(errors="replace"),
        "stderr": proc.stderr.decode(errors="replace"),
        "exit_code": proc.returncode,
        "execution_time_ms": elapsed
    }
```

**Detection of Shizuku status:**

rish requires the Shizuku app running and `RISH_APPLICATION_ID` set in the environment (per Shizuku's rish setup). Check availability:
```bash
which rish             # Returns path if installed
rish -c 'echo hello'   # If this returns "hello", Shizuku is running
```

If `which rish` fails or the Shizuku service is not running, return `SHIZUKU_NOT_RUNNING` error.

**Error states:**
- `SHIZUKU_NOT_RUNNING` — Shizuku service is not available
- `FORBIDDEN_COMMAND` — command matches blocklist pattern
- `TIMEOUT` — command did not complete within `timeout_sec`
- `RISH_ERROR` — rish process crashed or returned non-zero for internal reasons

### tools/sys_exec.py — `phone.system.termux_exec`

Execute a command inside Termux's native environment.

**Input:**
```json
{
  "command": "ls -la ~/ingest/",
  "timeout_sec": 30,
  "workdir": "~"
}
```

**Output:**
```json
{
  "stdout": "total 4\ndrwxr-xr-x ...",
  "stderr": "",
  "exit_code": 0,
  "execution_time_ms": 12
}
```

**Implementation:**

```python
async def termux_exec(command: str, timeout_sec: int = 30, workdir: str = "~") -> dict:
    # Expand ~ and $HOME
    workdir_expanded = os.path.expanduser(workdir)

    start = time.time()
    proc = subprocess.run(
        command,
        shell=True,
        cwd=workdir_expanded,
        capture_output=True,
        timeout=timeout_sec,
        executable="/data/data/com.termux/files/usr/bin/bash"
    )
    elapsed = int((time.time() - start) * 1000)

    return {
        "stdout": proc.stdout.decode(errors="replace"),
        "stderr": proc.stderr.decode(errors="replace"),
        "exit_code": proc.returncode,
        "execution_time_ms": elapsed
    }
```

**Important:** Use `executable="/data/data/com.termux/files/usr/bin/bash"` to ensure we run in Termux's bash, not Android's /system/bin/sh.

**Error states:**
- `TIMEOUT` — command did not complete within timeout_sec
- `WORKDIR_NOT_FOUND` — specified workdir doesn't exist
- `COMMAND_NOT_FOUND` — the command binary doesn't exist (check return code 127)

### tools/sys_free_ram.py — `phone.system.free_ram`

Free RAM by stopping non-critical background apps.

**Input:**
```json
{
  "target_free_mb": 2048,
  "aggressiveness": "normal"
}
```

**Output:**
```json
{
  "freed_mb": 2150,
  "available_mb": 6144,
  "killed_packages": ["com.android.chrome", "com.instagram.android"]
}
```

**Implementation:**

```python
# Apps to consider for killing (non-critical, high RAM usage)
KILL_CANDIDATES = [
    "com.android.chrome",
    "com.instagram.android",
    "com.facebook.katana",
    "com.twitter.android",
    "com.spotify.music",
    "com.google.android.youtube",
    "com.snapchat.android",
]

async def free_ram(target_mb: int, aggressiveness: str = "normal") -> dict:
    # 1. Current available RAM — /proc/meminfo is world-readable, no rish needed
    available_kb = parse_meminfo(Path("/proc/meminfo").read_text())

    if available_kb / 1024 >= target_mb:
        return {"freed_mb": 0, "available_mb": available_kb // 1024, "killed_packages": []}

    # 2. Stop candidates until target is met
    killed = []
    estimated_freed = 0

    kill_list = KILL_CANDIDATES
    if aggressiveness == "aggressive":
        kill_list += ADDITIONAL_KILL_CANDIDATES  # background services too; never system UI

    for pkg in kill_list:
        # Check if running (rish needed to see other apps' processes)
        pid_proc = await rish_call(f"pidof -s {pkg}")
        if pid_proc["exit_code"] != 0 or not pid_proc["stdout"].strip():
            continue  # Not running

        # Stop via rish: force-stop lets the app save state (safer than am kill)
        await rish_call(f"am force-stop {pkg}")

        # Loop-exit heuristic ONLY (~100MB/app assumption). The reported
        # freed_mb below comes from re-reading /proc/meminfo, not this.
        estimated_freed += 100
        killed.append(pkg)

        if estimated_freed >= target_mb:
            break

    # 3. Re-check available RAM — the authoritative freed_mb source
    final_available_kb = parse_meminfo(Path("/proc/meminfo").read_text())

    return {
        "freed_mb": max(0, (final_available_kb - available_kb) // 1024),
        "available_mb": final_available_kb // 1024,
        "killed_packages": killed
    }
```

**Notes:**
- `am force-stop` is safer than `am kill` — it lets the app save state
- `aggressiveness = "normal"` targets only user-facing apps
- `aggressiveness = "aggressive"` may also stop background services

**Error states:**
- `SHIZUKU_NOT_RUNNING` — rish is required for `pidof`/`am force-stop` on other packages (NOT for reading /proc/meminfo)
- `NO_APPS_TO_KILL` — all candidates are already stopped
- `INSUFFICIENT_TARGET` — even after stopping everything, can't reach target_free_mb

### tools/sys_notify.py — `phone.system.notify`

Send a system notification.

**Input:**
```json
{
  "title": "Audit Complete",
  "body": "Vulnerability found. PR generated.",
  "priority": "high",
  "click_action": null
}
```

**Output:**
```json
{
  "notification_id": 42
}
```

**Implementation:**

```python
import itertools, shlex

_notif_counter = itertools.count(1)

async def send_notification(title: str, body: str, priority: str = "normal",
                           click_action: Optional[str] = None) -> dict:
    if not title:
        raise ToolError("TITLE_EMPTY", "Android requires a non-empty title")

    # termux-notification prints nothing — generate the id ourselves and pass --id
    notification_id = next(_notif_counter)

    cmd = (f'termux-notification --id {notification_id} '
           f'--title {shlex.quote(title)} --content {shlex.quote(body)}')
    if priority == "high":
        cmd += " --priority high"
    if click_action:
        cmd += f" --action {shlex.quote(click_action)}"

    proc = await termux_exec(cmd)
    if proc["exit_code"] != 0:
        raise ToolError("NOTIFY_FAILED", f"Failed to send notification: {proc['stderr']}")

    return {"notification_id": notification_id}
```

**Priority mapping:**
- `high` → `termux-notification --priority high` (makes sound + heads-up display)
- `normal` → default notification (goes to notification shade silently)
- `low` → `termux-notification --priority low` (no sound, minimized)

**Error states:**
- `NOTIFY_FAILED` — termux-notification returned non-zero
- `TITLE_EMPTY` — empty title (Android requires a non-empty title)

---

## Test Procedure

Use the `mcp_call` helper from Phase 2's test procedure.

1. Test rish: `mcp_call phone.system.rish '{"command":"echo hello"}'` → `"stdout": "hello\n"`
2. Test blocklist: `mcp_call phone.system.rish '{"command":"rm -rf /"}'` → error `FORBIDDEN_COMMAND`
3. Test Termux exec: `mcp_call phone.system.termux_exec '{"command":"ls ~/ingest/"}'` → listing of ingest directory
4. Test free_ram: `mcp_call phone.system.free_ram '{"target_free_mb":512}'` → Chrome stopped (if running), RAM freed
5. Test notify: `mcp_call phone.system.notify '{"title":"Test","body":"Hello from MCP"}'` → notification appears in the status bar

---

## Acceptance Criteria

- [ ] `phone.system.rish` executes a safe command and returns output
- [ ] `phone.system.rish` rejects commands matching blocklist with `FORBIDDEN_COMMAND` (including variants like `rm -rf / --no-preserve-root`)
- [ ] `phone.system.rish` returns `SHIZUKU_NOT_RUNNING` when Shizuku is stopped
- [ ] `phone.system.termux_exec` runs commands in Termux environment
- [ ] `phone.system.free_ram` stops background apps and reports freed RAM from real meminfo delta
- [ ] `phone.system.free_ram` with target already met returns 0 freed
- [ ] `phone.system.notify` shows notification in status bar with the returned id
- [ ] `phone.system.notify` with priority "high" appears as heads-up

---

## Guardrails

- **Blocklist is a safety net, not a security boundary.** It prevents accidents, not attacks. A user who can edit the blocklist can remove entries.
- **`am force-stop`, not `am kill`.** Force-stop is safer (allows state save). Kill is SIGKILL and may leave app data in inconsistent state.
- **`free_ram` is advisory.** The freed_mb value comes from the `/proc/meminfo` delta. Android's LMK (Low Memory Killer) may reclaim differently.
- **Notifications respect Do Not Disturb.** `termux-notification` honors the phone's DND settings. High priority may still be suppressed if DND is set to "total silence."
- **Shizuku status is checked per-call.** Check `which rish` + liveness before every rish command. If Shizuku was stopped between calls, the tool returns the appropriate error.

---

## Git Commit

```bash
git add -A
git commit -m "feat(phone-mcp): system tools — rish, exec, free_ram, notify"
git tag phone-mcp-phase-5
git push origin phone
```

Rollback: `git revert HEAD`. System tools revert. All other functionality unaffected.
