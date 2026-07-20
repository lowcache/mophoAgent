# Phone MCP Server (Phases 0–5)

A persistent FastMCP Streamable-HTTP server that runs in Termux on the Galaxy S26 Ultra.

## Phase 5: system tools

Four system-level tools (`tools/sys_*.py`, shared plumbing in
`tools/sys_common.py`). `phone.system.rish` runs a command at shell uid
through Shizuku's rish — **Shizuku must be installed and running on the
phone; that is the operator's responsibility**, and rish must be on the
service PATH (`~/bin`, per run.sh). `phone.system.termux_exec` runs a command
in Termux's bash at the unprivileged Termux uid. `phone.system.free_ram`
`am force-stop`s non-critical background apps (never system UI, launcher,
Termux, Shizuku, or messengers) until `/proc/meminfo` MemAvailable reaches
the target; the reported `freed_mb` is the real meminfo delta, never the
~100 MB/app loop-exit estimate. `phone.system.notify` posts a notification
via `termux-notification` with a self-generated `--id` (D10).

Every command entering rish — including free_ram's internal `pidof` /
`am force-stop` — is screened against `config/rish_blocklist.txt` (one
**regex** per line, installed to `~/.config/phone-agent/` on first use and
re-read on mtime change). It is a safety net against accidents, **not a
security boundary**: anyone who can edit the file can empty it. Loading
fails **closed** — an unreadable or patternless blocklist raises
`BLOCKLIST_UNAVAILABLE` rather than letting rish run unscreened.
`termux_exec` is deliberately *not* blocklisted; it is an unrestricted
command primitive gated only by the bearer token and the tailnet (D1).

## Phase 4: sensor tools

Five single-shot hardware reads (`phone.sensor.read_{imu,modem,gps,light,proximity}`),
all CPU-only (no NPU). `read_imu` bursts accelerometer+gyroscope via
`termux-sensor` and runs an on-device activity inference
(`sensors/activity.py` — a pure-stdlib rule set over six statistical
features: mean/variance of accel magnitude, DFT peak frequency and
high/low energy ratio, gravity angle, zero-crossing rate) yielding
on_desk / in_hand / in_pocket / walking / stationary / unknown. `read_modem`
reads WiFi association + cellular type from Termux:API (RSRP is a
best-effort Shizuku/rish dumpsys read, null without Shizuku; first-hop
latency is a single ping). `read_gps` uses the cached last-known fix
(`termux-location -r last`, low power per D10) and tags the position against
`config/geofences.json` (ships empty; operator fills it — no fabricated
coordinates). `read_light`/`read_proximity` map raw sensor values to labels.
Device-specific sensor names are discovered once via `termux-sensor -l` and
cached in `~/.config/phone-agent/sensors.json` (`tools/sensor_common.py`).
Single-shot only — continuous monitoring belongs to Phase 7/8.

## Phase 3: processing pipelines

Three linear DAG pipelines (`pipeline/`) chain capture + NPU tools:
audio→transcript, image→OCR (EXIF/deskew correction, reading-order merge),
share→classify/extract/summarize/embed. Captures auto-trigger their
pipeline (`ingest/capture_trigger.py`, fire-and-forget; image shares route
to OCR); `phone.pipeline.run` triggers manually. Output JSON lands in
`~/ingest/processed/{transcripts,ocr,summaries}/`, failures in
`~/ingest/errors/` with partial context. URL extraction is a stdlib
`html.parser` scorer (`pipeline/extract_html.py`) — every readability
library needs lxml/C extensions, which cannot load in the bionic venv.
Summaries only for >500-word content, head-truncated to fit qwen's
1024-token context, skipped when the inference queue is saturated.
Liveness: `scripts/watchdog.sh` (external /health probe re-running
bootstrap; install via `scripts/watchdog-install.sh`, termux-job-scheduler
every 15 min) plus bootstrap's rish `max_phantom_processes` mitigation.

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
