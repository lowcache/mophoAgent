---
type: state
project: mophoAgent
last_updated: 2026-07-18
status: active
---

# System State

## Repository Structure
- **Branches:** `main` (integration base), `phone` (phases 0–7), `laptop` (phase 8)
- **Branch ownership:** claude-phone owns `phone` branch; claude-laptop owns `laptop` branch (phase 8) and all integration merges
- **Current commit state:**
  - `origin/phone` @ `2bcff48` (Phase 3 delivery relay, 2026-07-17)
  - local `phone` @ `c440d34` (Phase 3 sign-off + memory commits, 5 ahead / 0 behind — clean fast-forward)
  - `laptop` @ ce840a2; `main` @ fdbe9a7
- **Phase 1 status:** CLOSED (2026-07-16)
- **Phase 2 status:** CLOSED (2026-07-17)
- **Phase 3 status:** CLOSED (2026-07-18; pipelines verified 5/5 over tailnet)
- **Phase 4 status:** IN PROGRESS (sensor tools locally committed @ fa9d214, not pushed)

## Phase 3 Closure (2026-07-18) — Pipelines Verified
- **Deliverable:** Processing pipelines (audio→text, image→ocr, share→extract) + `phone.pipeline.run` manual tool; code @ `3fac7e2` (tag `phone-mcp-phase-3`)
- **Tool surface:** 12 tools (Phase 2: 11 capture/ingest; Phase 3: +1 pipeline.run)
- **Independent laptop verification over tailnet (100.101.229.9:8462), 2026-07-18:**
  - `/health` 200 ✓, bad bearer 401 ✓, `/tools/list` 12 tools ✓, `phone.system.ping` ✓, `phone.npu.embed` 384-dim norm ~1.0 ✓
  - Verification result: **5/5 PASS** (verify.sh independent run by laptop)
- **Pipeline implementations:**
  - `phone.pipeline.run` — multi-stage DAG: auto-trigger via browser share hooks, manual invocation, dispatch to workers (audio-transcript, image-ocr, share-extract)
  - Audio: Whisper-small (244M), Silero v5 VAD (offline); transcription + confidence output
  - Image: easyocr (GPU optional); detected text + bboxes
  - Share: HTML readability via stdlib `html.parser` scorer; Qwen2-0.5B summarize (2500 char input cap); Qwen2-0.5B embed (800 char cap)
- **Known trade-offs (documented in D13, D14):** Share truncation on long docs (>~500 words); stdlib readability scorer (no lxml in bionic venv)
- **Sign-off:** Laptop sign-off relay committed locally @ `relay/to-phone/20260718-phase3-signoff.md` (c440d34); push pending Phase 4 quiescence

## Phase 4 Status — IN PROGRESS (2026-07-18)
- **Scope:** Sensor tools (IMU, modem, GPS, light, proximity) + geofence configuration
- **Locally committed (not pushed as of 02:15 UTC):**
  - feat commit @ `fa9d214`: `phone/tools/sensor_{imu,modem,gps,light,proximity}.py` (5 tools); `config/geofences.json`; `phone/tools/sensor_common.py`
  - Delivery relay to laptop being written (Phase 4 handoff in progress)
- **Verification:** Factual API-correctness review active (verifying Termux-API D10 corrections against sensor files)
- **Expected next:** Relay commit + tag + push (imminent)

## Runtime Stabilization & Watchdog (Phase 3 Action Item) — PARTIALLY LIVE
- **Incident (2026-07-17, ~16:34 UTC):** Native runit supervision tree died after 12h+ idle (suspected phantom-process-killer)
- **Mitigation code delivered (Phase 3 @ 3fac7e2):**
  - `bootstrap.sh` phantom-process guard
  - `watchdog.sh` `/health` probe + restart logic
  - `watchdog-install.sh` → termux-job-scheduler job
- **Activation status:**
  - **#1 Install + verify: DONE (2026-07-18)** — Operator ran `watchdog-install.sh` in native session; `termux-job-scheduler --pending` confirms job present (ID: 4623; relay specified 462 — job ID discrepancy noted in mistakes.md)
  - **#2 Battery exemption: PENDING** — Termux + Termux:API must be set to Battery→Unrestricted (required for watchdog to survive idle kill; not yet confirmed)
  - **#3 Optional reboot check: PENDING** (deferred until #2 confirmed)
- **Defense status:** Watchdog code in place; job installed; battery exemption blocks full activation. Not yet shielded against phantom-process-killer without #2.

## Developer Monitoring (2026-07-18)
- **mopho-watch:** ADB screencap @ `~/.local/bin/mopho-watch`; PNG at `~/mopho/latest.png` (2s cadence). Capture verified working; frame read confirmed readable.
- **mopho-view:** Dual-session viewer (kitty claude + scrcpy on niri workspace "mopho"); keybind `Mod+Shift+V`. Not yet live-tested (deferred to preserve Phase 4 session).
- **Background monitor (bgbj2xnwk):** Polling `origin/phone` + `/health` every 40s; will wake on Phase 4 push or health drop. Active since 2026-07-18.

## phoneAgentBuild Organization
- `design/` — architecture specs (phone-mcp-tool-schema.md, npu-pipeline-graph.md, trigger-propagation-model.md, offline-autonomy-model.md, deepseek-system-prompt.md)
- `phone/` — phases 0–7: PHONE-ENV.md, `prompts/phase-{0..7}-*.md`, `tools/{sensor,capture,ingest,pipeline}*.py`, `config/geofences.json`
- `laptop/` — phase 8 NixOS module work
- `DECISIONS.md` — D1–D14 (design constraints and known limitations)
- `build-plan.md` — eight-phase structure with commit templates
- `scripts/verify.sh` — pre-merge battery (expect 12 tools as of Phase 3)

## Relay (relay/)
- `relay/to-laptop/` — phone→laptop; Phase 1–3 closures recorded; Phase 4 delivery in progress
- `relay/to-phone/` — laptop→phone; Phase 1–3 closures recorded; Phase 3 sign-off committed locally 2026-07-18
- `relay/archive/` — closed threads
- Protocol: markdown + frontmatter `type: blocker|question|decision-request|handoff|fyi`, edited only by author

## Tailscale Mesh & Networking
- **volnix microVM:** Tailnet-joined via auto-key; exit-node active; 100.101.229.9:8462 reachable from laptop; meshes to phone over Tailscale
- **NixOS vms.nix edits:** Pending `make switch` deployment (autostart, exit-node, NAT, static route 100.64.0.0/10)
- **USB tether metric:** Deployed via NetworkManager settings (metric 700, WiFi 600) 2026-07-18; durable across reboots
