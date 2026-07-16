# Phone MCP Server (Phase 0 skeleton + Phase 1 inference)

A persistent FastMCP Streamable-HTTP server that runs in Termux on the Galaxy S26 Ultra.

## Phase 1: inference runtime

Five NPU tools (`phone.npu.{transcribe,ocr,embed,classify,llm_infer}`) route
through a serialized priority queue (`npu/queue.py`) to persistent loopback
backends (D4): whisper-server :8465, llama-server --embedding :8464, and a
lazy llama-server :8463 shared by classify+llm (unloaded after 30s idle).
OCR runs in-process (onnxruntime CPU EP, PP-OCR rec model + numpy line
segmentation).

Backend binaries and their shared libraries live in
`~/phone-agent-runtime/{bin,lib}` (llama-server from the Termux `llama-cpp`
.deb; whisper-server built from source). numpy/Pillow/onnxruntime were
unpacked from Termux .debs straight into `.venv` — the dpkg database does
not know about any of this. To supersede the private runtime the operator
can run `pkg install llama-cpp python-numpy python-pillow python-onnxruntime`
natively and rebuild the venv with system-site-packages.

**The server must be launched with the runtime libs on the linker path:**

```bash
cd ~/phone-agent && LD_LIBRARY_PATH=$HOME/phone-agent-runtime/lib .venv/bin/python main.py
```

Model files (gitignored) live in `~/phone-agent/models/` — see
`npu/models.py` SPECS for the expected filenames. All backends are pinned
to 4 threads: on this big.LITTLE SoC more threads is dramatically slower
(whisper: 12s at `-t 4` vs 137s at `-t 8` for the same 11s clip).

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

Note on binding: with Tailscale connected, the server binds the configured
tailnet IP directly (verified, including self-curl of that IP). If the VPN
is down — e.g. early at boot — the address is unassigned and bind would
fail with `EADDRNOTAVAIL`, so the server probes it and falls back to
`0.0.0.0` with a warning rather than dying. The bearer token gates every
route except `/health`. DNS-rebinding protection in the MCP SDK is disabled
(it rejects non-localhost `Host` headers, breaking tailnet access; the
token middleware is the gate).

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
cd ~/phone-agent && LD_LIBRARY_PATH=$HOME/phone-agent-runtime/lib .venv/bin/python main.py >> ~/.config/phone-agent/server.log 2>&1
```
