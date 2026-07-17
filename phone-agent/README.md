# Phone MCP Server (Phase 0 skeleton + Phase 1 inference)

A persistent FastMCP Streamable-HTTP server that runs in Termux on the Galaxy S26 Ultra.

## Phase 1: inference runtime

Five NPU tools (`phone.npu.{transcribe,ocr,embed,classify,llm_infer}`) route
through a serialized priority queue (`npu/queue.py`) to persistent loopback
backends (D4): whisper-server :8465, llama-server --embedding :8464, and a
lazy llama-server :8463 shared by classify+llm (unloaded after 30s idle).
OCR runs in-process (onnxruntime CPU EP, PP-OCR rec model + numpy line
segmentation).

## Runtime contract (stabilization P0–P3, 2026-07-16)

Two environments; the boundary is binding (see `phoneAgentBuild/phone/PHONE-ENV.md`):
proot-distro is dev/orchestration only; native Termux owns the runtime and all
device I/O. The agent never launches servers or calls termux-api from proot.

Component provenance:

| component | source of truth | notes |
|---|---|---|
| llama-server | `pkg install llama-cpp` | `run.sh` falls back to `~/phone-agent-runtime/bin` |
| whisper-server | `~/phone-agent-runtime/bin` | **single explicit fallback** — not packaged in termux-main (checked 2026-07-16); source-built |
| numpy / Pillow / onnxruntime | `pkg install python-{numpy,pillow,onnxruntime}` | .deb payloads currently copied into `.venv`; retire by rebuilding the venv with `--system-site-packages` (operator, native) |

`scripts/run.sh` owns launch invariants: native-only fast-fail, explicit
`HOME`/`PATH` for the minimal Termux:Boot environment, existence checks, and
`LD_LIBRARY_PATH=$HOME/phone-agent-runtime/lib` (still required by
whisper-server and the venv-copied onnxruntime; drop only after those two
retire). Thread pinning (`-t 4 -tb 4`) stays in the backend spawn config.

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

The server runs as a supervised runit service (termux-services) installed by
a one-time native bootstrap:

```bash
# NATIVE Termux session (fast-fails under proot):
bash ~/mophoAgent/phone-agent/scripts/bootstrap.sh
```

That installs packages, wires `$PREFIX/var/service/phone-agent` → `scripts/run.sh`,
adds the Termux:Boot hook (wake-lock + start-services), enables and starts the
service, and waits for `/health` 200.

Lifecycle after bootstrap:
```bash
sv status phone-agent   # supervised state
sv down phone-agent     # stop
sv up phone-agent       # start (also restarts on crash automatically)
tail $PREFIX/var/log/sv/phone-agent/current   # service log
```

Manual launch (debug only, native session): `bash scripts/run.sh`

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

## Boot persistence

Handled by `scripts/bootstrap.sh`: Termux:Boot (companion app required) runs
`~/.termux/boot/start-services.sh`, which takes a wake-lock and starts
runsvdir; runit then brings up every enabled service, including `phone-agent`,
and restarts it on crash. No Automate flow or hand-written boot script needed.

## Pre-merge verify battery (P4)

`scripts/verify.sh [BASE_URL]` runs the acceptance battery (health 200,
bad-bearer 401, exact 7-tool list, ping, embed 384-dim/unit-norm) and exits
nonzero on any failure. Token from `$PHONE_AGENT_TOKEN` or
`~/.config/phone-agent/token`. The laptop runs it over the tailnet before
every phase merge:

```bash
scripts/verify.sh http://100.101.229.9:8462
```
