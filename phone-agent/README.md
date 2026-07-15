# Phase 0: MCP Server Skeleton

A persistent FastMCP Streamable-HTTP server that runs in Termux on the Galaxy S26 Ultra.

## Setup Instructions

1. Install Python and uv in Termux:
   ```bash
   pkg install python uv
   uv venv
   uv pip install -r pyproject.toml
   ```
   (`-r pyproject.toml` installs the dependency list without building the
   project itself — there is no build backend; the server runs from source.)

2. Generate the token file:
   ```bash
   mkdir -p ~/.config/phone-agent
   openssl rand -hex 32 > ~/.config/phone-agent/token
   ```

3. Create the `config.json`:
   ```bash
   mkdir -p ~/.config/phone-agent
   echo '{"tailscale_ip": "127.0.0.1"}' > ~/.config/phone-agent/config.json
   ```

## Running the Server

Start the server using the virtual environment:
```bash
.venv/bin/python main.py
```

## Test Procedure

1. Test `/health`:
   ```bash
   curl -s http://127.0.0.1:8462/health
   ```

2. Test `tools/list` (the MCP SDK requires the `Accept` header — omitting it
   returns a `-32600 Not Acceptable` JSON-RPC error):
   ```bash
   curl -s -H "Authorization: Bearer $(cat ~/.config/phone-agent/token)" \
     -H 'Content-Type: application/json' \
     -H 'Accept: application/json, text/event-stream' \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
     http://127.0.0.1:8462/mcp
   ```

3. Test `phone.system.ping`:
   ```bash
   curl -s -H "Authorization: Bearer $(cat ~/.config/phone-agent/token)" \
     -H 'Content-Type: application/json' \
     -H 'Accept: application/json, text/event-stream' \
     -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"phone.system.ping","arguments":{}}}' \
     http://127.0.0.1:8462/mcp
   ```

Note on binding: Android does not let userland bind the Tailscale VPN
address directly (`EADDRNOTAVAIL`), so the server probes the configured IP
and falls back to `0.0.0.0`. The bearer token gates every route except
`/health`. The phone cannot curl its own Tailscale IP (no VPN hairpin);
verify tailnet reachability from another peer.

## Automate flow creation steps

You can start the server on boot using the Automate app or Termux:Boot.

### Automate App
- Open Automate → New flow
- Add "Flow beginning" block (trigger: Device boot)
- Add "Wait" block (30 seconds)
- Add "Shell command" block: `am startservice -n com.termux/.app.TermuxService -a com.termux.service_start -e com.termux.execute_cmd 'cd ~/phone-agent && .venv/bin/python main.py'`
- Add "Loop" block (every 60s)
- Add "Shell command" block: `curl -sf http://127.0.0.1:8462/health` — if exit code != 0, restart

### Termux:Boot Alternative
Create `~/.termux/boot/phone-mcp.sh` (requires the Termux:Boot app):
```bash
#!/data/data/com.termux/files/usr/bin/sh
cd ~/phone-agent && .venv/bin/python main.py >> ~/.config/phone-agent/server.log 2>&1
```
