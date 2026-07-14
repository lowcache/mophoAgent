# Phase 5: System Tools

**Target Agent:** Claude Code (phone, Termux)
**Commit message:** `feat(phone-mcp): system tools — exec, free_ram, notify`

---

## What You Are Building

Three MCP tools for system-level operations: running commands in Termux, freeing RAM, and sending system notifications.

---

## Prerequisites

Phase 0 built.

---

## File Structure

```
~/.config/phone-agent/
├── tools/
│   ├── sys_exec.py                 # NEW: phone.system.termux_exec
│   ├── sys_free_ram.py             # NEW: phone.system.free_ram
│   ├── sys_notify.py               # NEW: phone.system.notify
```

---

## Implementation Spec

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

Free RAM by killing background apps (scoped down per D3: without Shizuku, we can only run `am kill-all` or kill Termux's own spawned processes).

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
  "killed_packages": []
}
```

**Implementation:**

```python
import subprocess

async def free_ram(target_mb: int, aggressiveness: str = "normal") -> dict:
    # 1. Get current available RAM
    with open("/proc/meminfo") as f:
        meminfo = f.read()
    available_kb = parse_meminfo(meminfo)

    if available_kb / 1024 >= target_mb:
        return {"freed_mb": 0, "available_mb": available_kb // 1024, "killed_packages": []}

    # 2. Run am kill-all to request Android to kill background cached processes
    subprocess.run(["am", "kill-all"], capture_output=True)

    # 3. Re-check available RAM
    with open("/proc/meminfo") as f:
        meminfo = f.read()
    final_available_kb = parse_meminfo(meminfo)

    return {
        "freed_mb": max(0, (final_available_kb - available_kb) // 1024),
        "available_mb": final_available_kb // 1024,
        "killed_packages": []
    }
```

**Notes:**
- The "freed_mb" is calculated from actual MemAvailable difference.

**Error states:**
- `INSUFFICIENT_TARGET` — even after killing everything, can't reach target_free_mb

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
async def send_notification(title: str, body: str, priority: str = "normal",
                           click_action: Optional[str] = None) -> dict:
    # Use termux-notification
    cmd = f'termux-notification --title {shlex.quote(title)} --content {shlex.quote(body)}'
    if priority == "high":
        cmd += " --priority high"
    if click_action:
        cmd += f" --action {shlex.quote(click_action)}"

    proc = await termux_exec(cmd)
    if proc["exit_code"] != 0:
        raise ToolError("NOTIFY_FAILED", f"Failed to send notification: {proc['stderr']}")

    # termux-notification returns the notification ID on stdout
    notification_id = int(proc["stdout"].strip())

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

1. Test Termux exec:
   ```bash
   echo '{"jsonrpc":"2.0","method":"tools/call","id":11,"params":{"name":"phone.system.termux_exec","arguments":{"command":"ls ~/ingest/"}}}' | ...
   ```
   → listing of ingest directory

4. Test free_ram:
   ```bash
   echo '{"jsonrpc":"2.0","method":"tools/call","id":12,"params":{"name":"phone.system.free_ram","arguments":{"target_free_mb":512}}}' | ...
   ```
   → Chrome killed (if running), RAM freed

5. Test notify:
   ```bash
   echo '{"jsonrpc":"2.0","method":"tools/call","id":13,"params":{"name":"phone.system.notify","arguments":{"title":"Test","body":"Hello from MCP"}}}' | ...
   ```
   → Notification appears in the status bar

---

## Acceptance Criteria

- [ ] `phone.system.termux_exec` runs commands in Termux environment
- [ ] `phone.system.free_ram` kills background apps and reports freed RAM
- [ ] `phone.system.free_ram` with target already met returns 0 freed
- [ ] `phone.system.notify` shows notification in status bar
- [ ] `phone.system.notify` with priority "high" appears as heads-up

---

## Guardrails

- **`free_ram` is advisory.** The freed_mb value is a best estimate from `/proc/meminfo`. Android's LMK (Low Memory Killer) may reclaim differently.
- **Notifications respect Do Not Disturb.** `termux-notification` honors the phone's DND settings. High priority may still be suppressed if DND is set to "total silence."

---

## Git Commit

```bash
git add -A
git commit -m "feat(phone-mcp): system tools — rish, exec, free_ram, notify"
git tag phone-mcp-phase-5
```

Rollback: `git revert HEAD`. System tools revert. All other functionality unaffected.
