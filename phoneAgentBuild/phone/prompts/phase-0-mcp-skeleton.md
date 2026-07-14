# Phase 0: MCP Server Skeleton

**Target Agent:** Claude Code (phone, Termux)
**Commit message:** `feat(phone-mcp): skeleton server with health/state/dispatch`

---

## What You Are Building

A persistent FastMCP Streamable-HTTP server per D1 that runs in Termux on the Galaxy S26 Ultra. It binds to the Tailscale IP on port 8462, registers tools, dispatches incoming calls, and returns responses. This is the foundation that every other phase builds on.

This phase produces **zero real functionality** — just the skeleton that proves the server starts, accepts connections, and responds to tool queries.

---

## Stack

- **Language:** Python 3.12+ (Termux)
- **Package manager:** uv (pip works too)
- **Transport:** MCP Streamable HTTP (FastMCP/uvicorn)
- **Dependencies:** mcp[cli]>=1.x, uvicorn, pydantic
- **No external dependencies yet** — no NPU, no sensors, no Shizuku

---

## File Structure

Create these files inside `~/phone-agent/` (per D2):

```
~/phone-agent/
├── main.py                    # Entry point — FastMCP server
├── tool_registry.py           # Tool registration + dispatch
├── tools/
│   ├── __init__.py
│   ├── health.py              # phone.system.state, phone.system.ping
├── config/
│   ├── __init__.py
│   └── settings.py            # Paths, constants
├── pyproject.toml             # Build config
├── README.md                  # Setup + test instructions
└── .gitignore                 # Ignore models/ and .venv/
```

**Plus Automate file (outside phone-agent dir):**
`$HOME/storage/downloads/mcp-server-start.flow` — Automate flow to start server on boot

---

## Implementation Spec

### main.py

Starts a FastMCP server using Streamable HTTP via uvicorn. Adds Starlette middleware to check the bearer token and an extra `/health` route for probes.

```python
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from config.settings import TAILSCALE_IP

# Create FastMCP instance
mcp = FastMCP("phone-mcp")

# Register tools from registry
from tool_registry import register_all
register_all(mcp)

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        auth = request.headers.get("Authorization")
        expected = get_token_from_file() # read from ~/.config/phone-agent/token
        if not auth or auth != f"Bearer {expected}":
            from starlette.responses import JSONResponse
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)

app = mcp.get_starlette_app()
app.add_middleware(BearerAuthMiddleware)

@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import sys
    if not token_file_exists():
        print("Error: ~/.config/phone-agent/token missing.", file=sys.stderr)
        sys.exit(1)
    uvicorn.run(app, host=TAILSCALE_IP, port=8462)
```
Note: MCP protocol handshake (initialize/tools/list) is handled by the SDK — do not hand-roll JSON-RPC.

### Tool Registry

A module that registers tools with the `FastMCP` instance. Use the `@mcp.tool()` decorator and specify names with dots (e.g., `name="phone.system.ping"`).

### tools/health.py

Two tools:

**`phone.system.ping`** — No input. Returns:
```json
{ "status": "ok", "timestamp": "2026-07-14T12:00:00.000Z", "uptime_sec": 3600 }
```

**`phone.system.state`** — No input. Returns the initial version (static values, no real sensor data yet):
```json
{
  "battery_pct": 100,
  "charging": true,
  "thermal_state": "cool",
  "available_ram_mb": 4096,
  "mcp_server_uptime_sec": 3600,
  "active_tools": [],
  "pending_queue_depth": 0
}
```

### pyproject.toml

```toml
[project]
name = "phone-mcp"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "mcp[cli]>=1.0.0",
    "uvicorn",
    "pydantic>=2.0",
]
```

### Automate Flow: `mcp-server-start.flow`

A simple Automate flow that:
1. Trigger: `sys.boot_completed`
2. Wait 30 seconds (for Termux to initialize)
3. Action: Start Termux session with `cd ~/phone-agent && .venv/bin/python main.py`
4. Monitoring: Check every 60s that `curl -sf http://127.0.0.1:8462/health` succeeds (or `pgrep -f "python main.py"` as fallback).
5. If not running: restart (max 3 attempts in 5 minutes)
6. If 3 failures: persistent notification "Phone MCP server failed to start"

Since Automate flow files are binary .flow format, provide instructions to create it manually:
- Open Automate → New flow
- Add "Flow beginning" block (trigger: Device boot)
- Add "Wait" block (30 seconds)
- Add "Shell command" block: `am startservice -n com.termux/.app.TermuxService -a com.termux.service_start -e com.termux.execute_cmd 'cd ~/phone-agent && .venv/bin/python main.py'`
- Add "Loop" block (every 60s)
- Add "Shell command" block: `curl -sf http://127.0.0.1:8462/health` — if exit code != 0, restart
- Flow files can be exported as JSON and stored in the repo for sharing

Termux:Boot is a simpler alternative if Automate proves flaky; same script.

---

## Test Procedure

1. Install Python + dependencies in Termux:
   ```bash
   pkg install python uv
   uv venv
   uv sync
   ```

2. Start the server manually:
   ```bash
   .venv/bin/python main.py
   ```

3. Test `/health`:
   ```bash
   curl -s http://127.0.0.1:8462/health
   ```

4. Test `tools/list`:
   ```bash
   curl -s -H "Authorization: Bearer $(cat ~/.config/phone-agent/token)" \
     -H 'Content-Type: application/json' \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
     http://$PHONE_TS_IP:8462/mcp
   ```
   Expected output contains `result.tools` array.

5. Test ping:
   ```bash
   curl -s -H "Authorization: Bearer $(cat ~/.config/phone-agent/token)" \
     -H 'Content-Type: application/json' \
     -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"phone.system.ping","arguments":{}}}' \
     http://$PHONE_TS_IP:8462/mcp
   ```
   Expected:
   ```json
   {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"{\"status\":\"ok\",\"timestamp\":\"...\",\"uptime_sec\":...}"}]}}
   ```
   Note: tool results are wrapped in `content[0].text`.

---

## Acceptance Criteria

- [ ] Server starts bound to TS IP
- [ ] `/health` endpoint returns 200 OK
- [ ] `tools/list` shows both tools
- [ ] `phone.system.ping` and `phone.system.state` return correct JSON
- [ ] Requests without bearer token get 401
- [ ] Malformed JSON handled by SDK (verify 400 not crash)
- [ ] Automate flow restarts server if it crashes (test by killing the process and checking restart within 60s)

---

## Guardrails

- **No real functionality yet.** Phase 0 is only the dispatch loop, health tools, and Automate orchestration.
- **No file I/O beyond `main.py` and tool imports.** Don't create the ingest directory yet.
- **No NPU, no sensor, no Shizuku.** Those start in Phases 1 and 2.
- **Log to ~/.config/phone-agent/server.log via stderr.**
- **Server must be killable with Ctrl+C.** Clean shutdown handling (save nothing, this is a stateless server).
- **Server must refuse to start without a token file (generate with openssl rand -hex 32 on first run).**

---

## Git Commit

```bash
cd ~/phone-agent/
git init
git add -A
git commit -m "feat(phone-mcp): skeleton server with health/state/dispatch"
git tag phone-mcp-phase-0
```

Rollback: `git revert HEAD` on this repo. Server is 6 files — no side effects.
