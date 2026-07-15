---
name: phone-mcp-verify
description: >-
  Runbook for booting a test instance of the phone-agent MCP server and running
  the acceptance battery (health, tools/list, auth 401s, malformed JSON 400).
  Use whenever a task touches phone-agent/ server code, middleware, or tools
  and needs verification before reporting.
---

# phone-agent MCP server — verification runbook

The live server owns port 8462 (Tailscale IP bind). Always test against a
throwaway instance on loopback with a different port.

## 1. Environment

A venv with `mcp` and `uvicorn` is required. If none is provided by the brief:

```bash
python3 -m venv "$SCRATCH/venv" && "$SCRATCH/venv/bin/pip" install -q mcp uvicorn
```

`curl` does not work under proot (`/system/bin/curl`: operation not permitted).
Use Python for all HTTP checks.

## 2. Boot a test instance

```bash
cd /root/mophoAgent/phone-agent
"$SCRATCH/venv/bin/python" -c \
  "from main import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=18462)" \
  > "$SCRATCH/testserver.log" 2>&1 &
sleep 4
```

## 3. Acceptance battery

Run with Python, e.g. `urllib.request` against `http://127.0.0.1:18462`.
Required headers for `/mcp`: `Content-Type: application/json` and
`Accept: application/json, text/event-stream`. Token:
`~/.config/phone-agent/token` (never print it).

| Check | Request | Expected |
|---|---|---|
| health | GET `/health`, no auth | 200 `{"status":"ok"}` |
| valid token | POST `/mcp` `tools/list`, `Authorization: Bearer <token>` | 200, all registered tools listed with non-empty descriptions |
| wrong token | `Authorization: Bearer wrongtoken` | 401 |
| missing token | no Authorization header | 401 |
| non-ASCII token | `Authorization: Bearer \xe9` | 401 (not 500) |
| malformed JSON | valid auth, body `{not json` | 400, server stays up |

After the battery: `grep -ci "traceback\|typeerror" "$SCRATCH/testserver.log"`
must be 0, and a repeated health check must still return 200.

## 4. Report

EVIDENCE must include the battery results table (actual status codes), the
grep count from the server log, and the exact commands used. If any check
deviates from Expected, that is a finding for RESULT — do not silently fix
beyond the brief's scope.

## 5. Cleanup

Kill the test server (`kill %1` or the saved PID). Leave the live server on
8462 untouched.
