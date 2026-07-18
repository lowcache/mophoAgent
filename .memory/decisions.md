---
type: decisions
project: mophoAgent
last_updated: 2026-07-17
status: active
---

# Architecture Decisions

## D1 — Transport Layer
MCP Streamable HTTP (FastMCP+uvicorn) running native Termux on port TS-IP:8462 with bearer token auth. Rejects stdio: phone server must persist across multiple client calls and handle concurrent requests from laptop and on-device inference tasks. Decision driven by model-reload cost and sessionless design constraint.

## D2 — Phone Build Environment  
Claude Code runs in proot-distro (Debian userland). Edit prompts and code from proot via bind mount; run the MCP server with native Termux Python (termux-api only works in native runtime). Proot provides full package ecosystem without root; native server keeps termux-api available.

## D3 — Cross-Device Communication
No SSH phone↔laptop. Phone→laptop only via Ollama HTTP API endpoint. Eliminates credential/session management, simplifies offline resilience (no connection state to manage), and reduces attack surface.

## D4 — Model Persistence
Llama-server and whisper-server run persistent (systemd services or task loop). Rejects per-call CLI spawns: avoids 2–5s model load overhead on every inference call and enables concurrent requests from multiple phone-side inference tasks.

## D5 — Processor Baseline and Stretch
CPU baseline (always available). NPU stretch goal (Snapdragon 8 Gen 3's Qualcomm Hexagon). QNN SDK not in Termux mainline; defer to future if llama.cpp adds QNN backend support. All phase prompts written to CPU path first, with placeholders for QNN ops.

## D6 — Staged File Transfer via Ingest Queue
New tools `phone.ingest.list` (list queued files) and `phone.ingest.fetch` (retrieve file bytes). Laptop runs ingest-sync timer that polls phone and copies files via MCP. Original plan omitted this layer; added in corrections to decouple capture timing from laptop poll interval.

## D7 — Proximity Semantics
Proximity=lock-only. Phone alerts when near laptop; user taps to unlock/sync. Rejects programmatic unlock (attack surface, UX confusion).

## D8 — NPU Preemption
No suspend/resume mid-inference (llama.cpp does not expose this). Instead: cancel+requeue. Voice wake-word preempts via priority queue; cancelled task requeued after voice session ends.

## D9 — Offline Detection Ladder
1. `curl http://127.0.0.1:8462/health` (local Ollama)
2. ICMP ping to laptop IP
3. ICMP ping to 1.1.1.1 (public DNS, no Tailscale CLI on Android)

If all fail, phone enters offline autonomous queue mode.

## D10 — Termux API Factual Corrections
- `termux-share-receive` does not exist; use `termux-url-opener` spool instead
- `termux-location -p once -r last` uses cached last-known fix, not fresh GPS lock (battery trade-off)
- `termux-sensor` requires `-d {interval_ms}` in addition to `-n {count}`
- `termux-notification` requires `--id` for persistence
- Light sensor: `SENSOR_NOT_AVAILABLE`, `SENSOR_DIRTY` error codes (not calibration)
- Blocklist: regex format, not shell globbing
- Queue directory: `phone-agent/delivering/` with persistent retry_count (JSON per task)
- Whisper model sizes: whisper-small=244M (not 94M), impacts storage/memory budget

## D11 — Runtime Boundary Separation
Proot-distro (Debian userland) reserved for dev only: editing prompts, cloning repos, git operations. Native Termux reserved for runtime: managed runit service lifecycle (termux-services), termux-api and device I/O calls, verification via loopback HTTP. Never launch the server or call termux-api from proot; this boundary prevents model-load overhead leakage into version control and ensures termux-api reliability.

## D12 — Developer Monitoring Strategy
Passive-and-advise model: user drives phone via scrcpy keybind (mopho-view), agent monitors via ADB screencap frames (mopho-watch) and advises on session health / tool correctness. No programmatic agent actuation on phone; all actions user-initiated. Decouples monitoring cadence from capture cadence for token efficiency.

## Branch and Integration Model
**Ownership:** Claude-phone owns `phone` branch (phases 0–7 only). Claude-laptop owns `laptop` branch (phase 8) and performs all integration merges to main. Main branch is integration-only (never direct commits from either agent).

**Workflow:**
1. Phone rebases `phone` on `main` at start of each phase
2. Phone commits phases to `phone` branch only
3. Laptop implements phase 8 on `laptop` branch
4. Laptop merges `phone` → `main` (fast-forward) after phone signals readiness via relay
5. Laptop merges `laptop` → `main` once phase 8 verified
6. Phone fast-forwards to `main` after each integration

**Relay protocol:** Cross-device collaboration via `relay/{to-laptop,to-phone,archive}/`. Each message is a markdown file on the author's branch (no cross-branch edits). Frontmatter: `type: blocker|question|decision-request|handoff|fyi`. Blocking issues filed in relay; no improvised architecture changes in code.

## Mechanical Edits via Tether
Design and prompt file corrections (spelling, config paths, factual corrections) delegated to tether/Gemini per brief. Laptop verifies output against DECISIONS.md before commit. Preserves laptop's architectural ownership while avoiding copy-paste overhead.
