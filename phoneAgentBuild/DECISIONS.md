# Build Decisions — Authoritative (resolves contradictions in the original docs)

Date: 2026-07-14. These decisions override anything contradicting them in
`design/`, `phone/prompts/`, or `laptop/`. Every edit applied to those files
traces back to a D-number here.

## D1 — Transport: MCP Streamable HTTP. stdio is dead.

The phone MCP server is a **persistent** process. A per-call stdio spawn (as
Phase 8's SSH examples assumed) would reload NPU/LLM models and lose queue,
session, and scheduler state on every call — it defeats the entire
architecture. Decided:

- Python `mcp` SDK (FastMCP) serving **Streamable HTTP** via uvicorn.
- Bind to the phone's Tailscale IP, port **8462**.
- Plain `GET /health` endpoint (no auth) for liveness probes.
- Auth: static bearer token at `~/.config/phone-agent/token`, checked as
  `Authorization: Bearer <token>` middleware. Tailscale provides network
  isolation; the token guards against anything else on the tailnet. The
  original "Tailscale peer TLS cert identity" idea is out — the Tailscale
  CLI/LocalAPI is not reachable from Termux (Android Tailscale is a VPN app,
  no CLI).

## D2 — Agents and where code lives

- Phone side is built by **Claude Code running in Termux under proot-distro**
  (not Codex — all "Target Agent: Codex" headers are stale).
- The server itself must run under **native Termux Python**, not proot,
  because `termux-api` binaries (microphone, camera, sensors, notification,
  location) only work in the native environment. Claude Code edits files from
  proot via a bind mount of the Termux home; it runs/tests the server with
  the Termux-side interpreter (see `phone/PHONE-ENV.md`).
- Layout (reconciled with the branch model): the **mophoAgent repo** is
  cloned into the native Termux home as `~/mophoAgent`; phone product code
  lives in `~/mophoAgent/phone-agent/` and is committed on the **`phone`
  branch** so phone and laptop commits never collide. A symlink
  `~/phone-agent -> ~/mophoAgent/phone-agent` makes every phase's
  `~/phone-agent/…` path resolve. Config: `~/.config/phone-agent/`. Models:
  `~/phone-agent/models/` (gitignored). The original
  "`git init ~/.config/phone-agent`" layout (code+repo inside .config) is out.

## D3 — No SSH anywhere in the phone↔laptop path

The design constraint ("MCP is the only interface, no side channels, no SSH")
wins over Phase 8's SSH-based examples. Concretely:

- Laptop → phone: HTTP MCP calls to `http://<phone-ts-ip>:8462` (curl or
  mcp-gateway HTTP client). Never `ssh phone 'python main.py'`.
- Phone → laptop: exactly one channel, the laptop's **Ollama HTTP API**
  (`http://volnix.<tailnet>.ts.net:11434`) for deep-path LLM queries and
  health probes. The phone holds no SSH keys (guardrail #2). The scheduler's
  `ssh volnix 'ollama list'` becomes `curl .../api/tags`.
- Deployment: no rsync-over-ssh. The repo is built on the phone by Claude
  Code; the laptop never writes to the phone's filesystem.

## D4 — Persistent inference runtimes, not per-call CLI spawns

Spawning `llama-cli`/`whisper-cli` per request reloads the model each time
(seconds of latency) and makes every TTFT target fiction. Decided:

- llama.cpp **`llama-server`** (OpenAI-compatible HTTP, localhost only) for
  LLM infer, classify, and embeddings; managed as child processes by
  `npu/bridge.py`.
- whisper.cpp **`whisper-server`** for transcription (or `pywhispercpp`
  bindings if they build cleanly on Termux).
- Classification confidence comes from `llama-server`'s `n_probs`/logprobs on
  the label token — subprocess CLI cannot expose logits at all.
- The separate `intent-classifier-v1` model is dropped for now; classify is a
  constrained prompt against qwen2.5-1.5b. Revisit a dedicated model later.

## D5 — CPU baseline, NPU stretch goal

There is no merged QNN backend in mainline llama.cpp (`-DLLAMA_QNN=ON` does
not exist), and Qualcomm QNN/SNPE SDKs are not packaged for Termux. Getting
NPU access from Termux userland is research, not a build step. Decided:

- Phase 1 acceptance criteria are **CPU** numbers: 10s audio transcribed
  ≤ 10s; embedding ≤ 300ms; LLM TTFT ≤ 1s with server warm. NPU targets
  (transcribe ≤ 5s, TTFT ≤ 50ms) are stretch goals, attempted only after the
  CPU baseline is committed, likely via onnxruntime QNN EP if its Android
  libs can be made to load. Every response reports `"backend"` so callers
  can tell which path served them.
- Correction of fact: whisper-small is ~244M params (not 94M).

## D6 — Ingest transfer mechanism (was missing entirely)

Phase 8 watched a local `~/ingest/staged/` on the laptop, but nothing ever
moved files off the phone. Decided: two new phone MCP tools —

- `phone.ingest.list` — input `{ "since": iso8601|null, "limit": int }`,
  output `{ "files": [{ "name", "size_bytes", "sha256", "pipeline",
  "created_at" }] }`, listing `~/ingest/staged/`.
- `phone.ingest.fetch` — input `{ "name": str, "delete_after": bool }`,
  output `{ "name", "sha256", "content_b64" }`. Staged outputs are JSON of
  modest size; base64 over MCP is fine. `delete_after: true` moves the
  phone-side file to `~/ingest/delivered-staged/`.

Laptop side runs an **ingest-sync systemd timer** (every 2 min when phone
reachable) that lists+fetches into the laptop's `~/ingest/staged/`, verifying
sha256. The existing path-unit watcher then processes local files as designed.
Tool count is now 21 core tools + phase-added tools (pipeline.run, voice.*,
queue.*, scheduler.*).

## D7 — Proximity is lock-only

`niri msg action lock-screen` exists; programmatic *unlock* is not a thing
(session lockers are designed so you cannot bypass auth; killing the locker
is a hole, not a feature). The proximity daemon locks on desk-departure and
does nothing on return (option `allowUnlock` exists, default false, marked
experimental with the security caveat). Auto-unlock ideas move to a future
UWB/BLE-attestation investigation.

## D8 — No NPU suspend/resume preemption

Inference backends have no suspend primitive. "Suspend batch inference,
save intermediate state to temp buffer, resume later" is fiction. Decided:
priority queue orders *pending* work only. Optionally, an interactive arrival
may **cancel** a running batch request (kill/abort HTTP request) and requeue
it from scratch. `trigger-propagation-model.md` concurrency rule 2 and
Phase 1's preemption paragraph are rewritten to match.

## D9 — Offline detection without the Tailscale CLI

`tailscale ping` / `tailscale status` don't exist on the phone (D1 note).
Detection ladder, implemented in `offline/detector.py`:

1. `curl -m 2 http://volnix.<tailnet>.ts.net:11434/api/version` → ONLINE.
2. else ICMP `ping -c1 -W2 <laptop-ts-ip>` ok but step 1 failed → laptop up,
   Ollama down → degraded-ONLINE (treat as LAPTOP_ASLEEP for routing).
3. else `ping -c1 -W2 1.1.1.1` ok → LAPTOP_UNREACHABLE (laptop asleep or
   tailnet down — indistinguishable without the CLI; poll every 60s).
4. else → NO_INTERNET (airplane mode etc.; poll every 120s).

## D10 — Misc corrections applied everywhere

- Share-sheet capture: `termux-share-receive` does not exist. The real
  mechanism is Termux's `~/bin/termux-url-opener` (and `termux-file-editor`)
  hook scripts, which Termux invokes when content is shared to it. Hook
  script writes into `~/ingest/shares/spool/`; `phone.capture.share` polls
  the spool with a timeout. (The original doc's "FIFO fallback" is now the
  primary, minus Automate.)
- Audio capture: primary is `termux-microphone-record` (file-based) +
  post-hoc VAD trim. Live VAD-gated streaming needs a mic stream Termux
  doesn't reliably give Python; it's an optional upgrade (pulseaudio source),
  not the baseline. Mic permission is an Android app permission on
  Termux:API — `termux-setup-storage` has nothing to do with it.
- Screenshot: `screencap` requires shell uid → **always rish**; there is no
  "direct" path from Termux uid.
- Current-connection WiFi info: `termux-wifi-connectioninfo` (scaninfo lists
  neighbors, not the current association).
- Sensors: `termux-sensor -s` takes comma-separated names which are
  device-specific — discover with `termux-sensor -l` at setup and store the
  mapping in config. `-d` is delay-ms, `-n` count.
- Location: `termux-location -r last` (cached, low power) vs `-r once -p
  gps` (fresh fix). The original `-p once -r last` mixed the flags up.
- Notifications: `termux-notification` does not print an ID; generate the id
  and pass `--id <n>` explicitly.
- EXIF: use public `Image.getexif()`, not `_getexif()`.
- `/proc/meminfo` is world-readable — no rish needed to read it.
- Blocklist matching: exact-string fnmatch of `"rm -rf /"` never matches
  `"rm -rf / --no-preserve-root"`. Blocklist is now **regex per line**,
  matched with `re.search` against the un-lowercased command.
- Queue dirs: layout must include `queue/delivering/` (Phase 2 SUBDIRS missed
  it). `QueueManager.fail()` must write the incremented `retry_count` back to
  the JSON file before renaming, or retries loop forever.
- Scheduler results path standardized: `~/ingest/processed/scheduled/`.
- Scheduler `flake_check` cannot run `nix` on the phone (no nix in Termux
  baseline): it polls the GitHub API for nixpkgs/flake-input movement and
  queues a summary for the laptop. `model_preload` uses the Ollama HTTP API.
- JSON config examples must be valid JSON — no `#` comments.
- `qwen` chat template / tokenizer comes with the GGUF; no extra dep.
- Wake word: highest-risk feature on the phone (background mic in Termux).
  Build order inside Phase 6 is TTS → router → session with a *manual*
  trigger tool (`phone.voice.ask`) → wake word last, marked experimental.
