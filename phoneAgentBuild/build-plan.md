# Project Build Plan — Phone Agent Integration

## Structure

Eight phases. Each phase is:
1. A self-contained system prompt you feed to an agent (Claude Code in Termux for phone-side, Claude Code for laptop-side)
2. Produces working, testable code
3. Gets its own git commit — rollback is one `git revert` away
4. Builds on previous phases but doesn't break them

## Decisions
- D1: Transport: MCP Streamable HTTP.
- D2: Agents and where code lives.
- D3: No SSH anywhere in the phone↔laptop path.
- D4: Persistent inference runtimes, not per-call CLI spawns.
- D5: CPU baseline, NPU stretch goal.
- D6: Ingest transfer mechanism (was missing entirely).
- D7: Proximity is lock-only.
- D8: No NPU suspend/resume preemption.
- D9: Offline detection without the Tailscale CLI.
- D10: Misc corrections applied everywhere.
(See DECISIONS.md for full details)

---

## Phase 0: MCP Server Skeleton (Phone-Side)
**Agent:** Claude Code (phone, Termux)
**Time:** ~1 session
**Commit message:** `feat(phone-mcp): skeleton server with health/state/dispatch`

Foundation of everything. A FastMCP Streamable HTTP server running in Termux, binding to the Tailscale IP on port 8462, with health/state/ping tools (no stdio) per D1. Has no real NPU or sensor backing yet.

**Files created:**
- `~/phone-agent/main.py` — entry point
- `~/phone-agent/tool_registry.py` — tool registration + dispatch
- `~/phone-agent/tools/health.py` — `phone.system.state`, `phone.system.ping`
- `~/phone-agent/pyproject.toml` — dependencies
- `automate/mcp-server-start.flow` — Automate flow to start server on boot
- `TERMUX_HOME/.profile` hook for PATH

**Output:**
```
$ curl -s -H "Authorization: Bearer $(cat ~/.config/phone-agent/token)" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  http://$PHONE_TS_IP:8462/mcp
```

**Rollback:** `git revert HEAD` — only these 6 files exist. No side effects.

---

## Phase 1: NPU Inference Layer (Phone-Side)
**Agent:** Claude Code (phone, Termux)
**Time:** ~2 sessions
**Commit message:** `feat(phone-mcp): NPU inference — whisper, ocr, embed, classify`

The NPU runtime bridge. Loads models into NPU memory, runs inference serially via priority queue. All 4 NPU compute tools become functional with real model backends.

**Files created:**
- `mcp-server/npu/bridge.py` — NPU runtime singleton, model lifecycle
- `mcp-server/npu/models.py` — model definitions (paths, quant levels, max context)
- `mcp-server/npu/queue.py` — priority inference queue (interactive > scheduled > batch)
- `mcp-server/tools/transcribe.py` — `phone.npu.transcribe`
- `mcp-server/tools/ocr.py` — `phone.npu.ocr`
- `mcp-server/tools/embed.py` — `phone.npu.embed`
- `mcp-server/tools/classify.py` — `phone.npu.classify`
- `mcp-server/tools/infer.py` — `phone.npu.llm_infer`

**Dependencies installed:**
- llama.cpp llama-server + whisper.cpp whisper-server (CPU baseline per D5; QNN/onnxruntime-QNN as stretch)
- ONNX Runtime for NPU

**Test:** `curl` a transcribe call with a test WAV file. Check processing time < 10s for 10s audio on CPU (< 5s NPU stretch).

**Rollback:** `git revert HEAD` — reverts the NPU layer. Phase 0 still works.

---

## Phase 2: Capture Tools (Phone-Side)
**Agent:** Claude Code (phone, Termux)
**Time:** ~1 session
**Commit message:** `feat(phone-mcp): capture tools — audio, image, screenshot, share`

Microphone capture, camera capture, screenshot via Shizuku, and share sheet listener. Creates the `~/ingest/` directory structure.

**Files created:**
- `mcp-server/tools/capture_audio.py` — `phone.capture.audio` + VAD
- `mcp-server/tools/capture_image.py` — `phone.capture.image`
- `mcp-server/tools/capture_screenshot.py` — `phone.capture.screenshot` (rish)
- `mcp-server/tools/capture_share.py` — `phone.capture.share` (Termux share-receive via am)
- `mcp-server/ingest/store.py` — file naming, directory layout writer
- `mcp-server/vad/` — Silero VAD model + gating logic

**Test:** Run `phone.capture.audio`, speak for 5s, check file appears in `~/ingest/audio/`.

**Rollback:** `git revert HEAD` — capture tools gone, but NPU inference and server still work.

---

## Phase 3: Processing Pipelines (Phone-Side)
**Agent:** Claude Code (phone, Termux)
**Time:** ~2 sessions
**Commit message:** `feat(phone-mcp): processing pipelines — audio→text, image→ocr, share→extract`

The three pipeline DAGs that chain capture + NPU compute tools into end-to-end transforms. Writes structured output to `~/ingest/processed/`.

**Files created:**
- `mcp-server/pipeline/executor.py` — thread pool executor with DAG stage runner
- `mcp-server/pipeline/audio_transcript.py` — Pipeline 1 (VAD → Whisper → format)
- `mcp-server/pipeline/image_ocr.py` — Pipeline 2 (orientation → OCR → order)
- `mcp-server/pipeline/share_extract.py` — Pipeline 3 (classify → extract → summarize → embed)
- `mcp-server/pipeline/format.py` — output formatters for each pipeline
- `mcp-server/ingest/capture_trigger.py` — Auto-start pipeline when capture completes

**Test:** Record audio → auto-transcribe → check `~/ingest/processed/transcripts/` has a JSON with correct structure.

**Rollback:** `git revert HEAD` — pipelines revert, but individual capture + NPU tools still work independently.

---

## Phase 4: Sensor Tools (Phone-Side)
**Agent:** Claude Code (phone, Termux)
**Time:** ~1 session
**Commit message:** `feat(phone-mcp): sensor tools — IMU, modem, GPS, light, proximity`

All 5 sensor tools become functional. IMU includes on-device activity inference (on_desk, walking, in_pocket, etc.).

**Files created:**
- `mcp-server/tools/sensor_imu.py` — `phone.sensor.read_imu` + activity classifier
- `mcp-server/tools/sensor_modem.py` — `phone.sensor.read_modem` (rish for hidden APIs)
- `mcp-server/tools/sensor_gps.py` — `phone.sensor.read_gps` (Termux:API)
- `mcp-server/tools/sensor_light.py` — `phone.sensor.read_light`
- `mcp-server/tools/sensor_proximity.py` — `phone.sensor.read_proximity`
- `mcp-server/sensors/activity.py` — IMU activity inference model
- `config/geofences.json` — geofence definitions

**Test:** `phone.sensor.read_imu` returns `{"inference": "on_desk", "confidence": 0.95}`.

**Rollback:** `git revert HEAD`

---

## Phase 5: System Tools (Phone-Side)
**Agent:** Claude Code (phone, Termux)
**Time:** ~1 session
**Commit message:** `feat(phone-mcp): system tools — rish, exec, free_ram, notify`

The remaining system tools. `phone.system.rish` with command blocklist. `phone.system.free_ram` with aggressiveness levels. `phone.system.notify` for phone notifications.

**Files created:**
- `mcp-server/tools/sys_rish.py` — `phone.system.rish` with command safety filter
- `mcp-server/tools/sys_exec.py` — `phone.system.termux_exec`
- `mcp-server/tools/sys_free_ram.py` — `phone.system.free_ram`
- `mcp-server/tools/sys_notify.py` — `phone.system.notify`
- `config/rish_blocklist.txt` — blocked commands (rm -rf /, etc.)

**Test:** `phone.system.rish` with `echo hello` returns `{"stdout": "hello\n"}`. `phone.system.rish` with `rm -rf /` returns `FORBIDDEN_COMMAND` error.

**Rollback:** `git revert HEAD`

---

## Phase 6: Voice AI + Offline Autonomy (Phone-Side)
**Agent:** Claude Code (phone, Termux)
**Time:** ~2 sessions
**Commit message:** `feat(phone-mcp): voice AI session + offline autonomy queue`

The interactive voice AI session state machine (wake word → listen → transcribe → route → TTS) and the full offline queue (pending/delivering/delivered/failed with priority delivery).

**Files created:**
- `mcp-server/voice/session.py` — voice AI session manager with wake word
- `mcp-server/voice/wake_word.py` — always-on wake word detection (NPU)
- `mcp-server/voice/tts.py` — local TTS engine
- `mcp-server/voice/router.py` — route to local NPU vs laptop Ollama
- `mcp-server/queue/manager.py` — queue state machine
- `mcp-server/queue/delivery.py` — delivery protocol with retry + ack
- `mcp-server/tools/queue_sync.py` — `phone.queue.sync`
- `mcp-server/tools/queue_deliver.py` — `phone.queue.deliver`
- `mcp-server/tools/queue_clear.py` — `phone.queue.clear_failed`
- `mcp-server/offline/detector.py` — disconnection mode detection
- `mcp-server/offline/mode.py` — local-only mode behavior changes

**Test:** Simulate laptop disconnect. Queue items. Reconnect. Verify delivery.

**Rollback:** `git revert HEAD`

---

## Phase 7: Subconscious Scheduler (Phone-Side)
**Agent:** Claude Code (phone, Termux)
**Time:** ~1 session
**Commit message:** `feat(phone-mcp): subconscious scheduler with cron trigger`

The event-driven scheduler loop. Trigger conditions (time-based, event-based), task definitions, execution, result logging.

**Files created:**
- `mcp-server/scheduler/engine.py` — scheduler event loop
- `mcp-server/scheduler/tasks.py` — task definitions (flake_check, model_preload, health_check, gc)
- `mcp-server/scheduler/triggers.py` — trigger sources (cron, event, sensor threshold)
- `config/scheduler_tasks.json` — user-configured task definitions

**Test:** Schedule a task. Verify it executes at the correct time. Verify result logged.

**Rollback:** `git revert HEAD`

---

## Phase 8: Laptop-Side Integration
**Agent:** Claude Code
**Time:** ~2 sessions
**Commit message:** `feat(laptop): NixOS module, mcp-gateway peer, agent hooks`

The laptop-side NixOS module that declares the phone agent as a known MCP peer, the systemd service that pulls ingest output via the two new phone tools (phone.ingest.list / phone.ingest.fetch), and the agent behavior changes for lock-only proximity per D7 and Network Context Engine.

**Files created:**
- `nixos/phone-agent/default.nix` — NixOS module for phone MCP peer
- `nixos/phone-agent/mcp-gateway.nix` — mcp-gateway registration
- `nixos/phone-agent/ingest-sync.nix` — systemd timer pulling phone.ingest.list/fetch per D6
- `nixos/phone-agent/ingest-watcher.nix` — systemd path unit for polling staged
- `nixos/phone-agent/proximity/` — niri lock hooks, theme adaptation
- `nixos/phone-agent/network-routing.nix` — net-gate routing policy from modem data
- `nixos/phone-agent/README.md` — setup instructions

**Rollback:** Remove `./nixos/phone-agent/` and add `imports = [];` back. NixOS rebuild reverts cleanly.

---

## Phase Dependency Graph

```
Phase 0 ─── MCP Server Skeleton
   │
   ├──► Phase 1 ─── NPU Inference Layer
   │       │
   │       ├──► Phase 2 ─── Capture Tools
   │       │       │
   │       │       └──► Phase 3 ─── Processing Pipelines
   │       │
   │       └──► Phase 4 ─── Sensor Tools
   │
   ├──► Phase 5 ─── System Tools
   │
   └──► Phase 6 ─── Voice AI + Offline Autonomy
            │
            └──► Phase 7 ─── Subconscious Scheduler
                              │
                              └──► Phase 8 ─── Laptop-Side Integration
```

Phases 1-5 can build in any order after Phase 0. Phase 6 depends on Phase 1 (NPU layer for Whisper) and Phase 5 (notify). Phase 7 depends on Phase 6 (queue for offline results). Phase 8 depends on Phases 4 (sensor tools for proximity/modem), 5 (system tools), and 7 (scheduler integrations).

---

## What You Get Per Rollback Point

| Phase | If it breaks, you roll back |
|---|---|
| 0 | The whole MCP server. Nothing else depends if you haven't built further. |
| 1 | NPU inference. Capture/voice/sensors still work with "NPU not available" fallback. |
| 2 | Capture tools. Ingest directory remains but stops receiving new files. |
| 3 | Pipelines. Individual tools still work independently. |
| 4 | Sensor tools. All other functionality unaffected. |
| 5 | System tools (rish, free_ram, notify). Voice AI loses notifications. |
| 6 | Voice AI + offline queue. Scheduler loses offline delivery. |
| 7 | Scheduler. Everything else continues. |
| 8 | Laptop integration. Phone side continues working autonomously. |

Each rollback is a single `git revert <phase-commit-hash>`. No cascading failures.
