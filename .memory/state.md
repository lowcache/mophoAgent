---
type: state
project: mophoAgent
last_updated: 2026-07-19
status: active
---

# System State

## Repository Structure
- **Branches:** `main` (integration base), `phone` (phases 0–7), `laptop` (phase 8)
- **Branch ownership:** claude-phone owns `phone` branch; claude-laptop owns `laptop` branch (phase 8) and all integration merges
- **Current commit state:**
  - `origin/phone` @ `e8f2487` (Phase 4 fixes delivered + relay pushed, 2026-07-19)
  - local `phone` @ 4 commits ahead (memory notes + rebase of fixes; sync-ready)
  - `laptop` @ ce840a2; `main` @ fdbe9a7
- **Phase 1 status:** CLOSED (2026-07-16)
- **Phase 2 status:** CLOSED (2026-07-17)
- **Phase 3 status:** CLOSED (2026-07-18; pipelines verified 5/5 over tailnet; sign-off pushed @ eca7716)
- **Phase 4 status:** IN PROGRESS (deployed live 17 tools; on-device sensor validation gate active; proximity/modem fixes verified & pushed)

## Phase 3 Closure & Sign-off (2026-07-18)
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
- **Laptop sign-off:** Relayed to phone; sign-off relay pushed to origin/phone @ `eca7716` (clean fast-forward, 2026-07-18)
- **Status:** ✅ **FULLY CLOSED** (sign-off and relay pushed to origin)

## Phase 4 Status — IN PROGRESS (2026-07-18/2026-07-19)
- **Scope:** Sensor tools (IMU, modem, GPS, light, proximity) + geofence configuration
- **Delivered:** `fa9d214` (sensor_*.py, geofences.json, sensor_common.py); `8428470` (relay to laptop); tag `phone-mcp-phase-4`. Pushed to origin 2026-07-18.
- **Live deployment:** Phase 4 code merged to native runtime via merge --ff-only + runit restart. `/health` 200, **17 tools live** (was 12 Phase 3 + 5 sensor tools). Server restart clean; no repeat of 2026-07-17 idle-death failure.
- **Independent laptop verification post-deploy, 2026-07-18:**
  - `verify.sh` run: **5/5 PASS @ 17 tools**. All sensor tools accessible (phone.sensor.read_imu, phone.sensor.read_modem, phone.sensor.read_gps, phone.sensor.read_light, phone.sensor.read_proximity).
- **On-device sensor acceptance gate (in progress 2026-07-18/2026-07-19):**
  - Operator running live sensor reads to validate behavior (desk→on_desk classification, walk→walking, modem SSID/signal, GPS, light lux, proximity cm).
  - **Bugs found and fixed:**
    1. **Proximity sensor:** Substring match for "proximity" caught "Touch Proximity Sensor" (touchscreen palm-rejection virtual sensor), not physical IR proximity (STK33F15 chip). Virtual sensor returns `READ_ERROR` on single `-n 1` read. Fix applied (2026-07-19, commit 17c239d): `_ROLE_EXCLUDE = {"proximity": ("touch",)}` filter added; full sensor list persisted during discovery for ground-truth reference and diagnosis.
    2. **Modem network_type:** `termux-telephony-deviceinfo` returns numeric constant 18 (IWLAN / WiFi-calling); sensor_common.py string map did not include it. Fix applied (2026-07-19, commit 17c239d): `NUMERIC_CELL_TYPES` map extended to cover all known Android constants (13→LTE, 18→IWLAN, 20→5G_NR, etc.); fallback chain: `CELL_TYPES → NUMERIC → upper()` for robustness.
  - **Fix delivery:** Commits `e8f2487` (relay delivery), `17c239d` (sensor fixes) pushed to origin/phone 2026-07-19.
- **Verification status (2026-07-19):**
  - Endpoint reachable: HTTP 200 ✓ (phone restarted tailscale; prior connectivity loss was transient).
  - Laptop prepared: local `phone` branch rebased cleanly onto origin/phone fixes + 4 memory commits; 0 behind origin.
  - `verify.sh` ready to execute; currently blocked only on auth token (~/.config/phone-agent/token, gitignored bearer token for HTTP header authentication).
  - Awaiting: (a) token provisioned, (b) verify.sh execution (expect 5/5 @ 17 tools), (c) on-device sensor reads confirm fixes green, (d) Phase 4 sign-off relay sent.

## Runtime Stabilization & Watchdog (Phase 3 Action Item) — FULLY LIVE
- **Incident (2026-07-17, ~16:34 UTC):** Native runit supervision tree died after 12h+ idle (suspected phantom-process-killer)
- **Mitigation code delivered (Phase 3 @ 3fac7e2):**
  - `bootstrap.sh` phantom-process guard
  - `watchdog.sh` `/health` probe + restart logic
  - `watchdog-install.sh` → termux-job-scheduler job
- **Activation status (all confirmed on-device 2026-07-18):**
  - **#1 Install + verify: DONE** — Operator ran `watchdog-install.sh` in native session; `termux-job-scheduler --pending` confirms job 462 present. ✅ CONFIRMED (corrected ID from relay typo)
  - **#2 Battery exemption: DONE** — Termux + Termux:API set to Battery → Unrestricted. ✅ CONFIRMED
  - **#3 Optional reboot check: DEFERRED** (Termux:Boot → /health 200 → shared-URL lands in processed/summaries; nice-to-have, not blocking)
- **Defense status:** ✅ **FULLY LIVE** (watchdog job 462 active; battery exemption confirmed; idle-death defense now in force against phantom-process-killer)

## Developer Monitoring (2026-07-18)
- **mopho-watch:** ADB screencap @ `~/.local/bin/mopho-watch`; PNG at `~/mopho/latest.png` (2s cadence). Capture verified working; frame read confirmed readable.
- **mopho-view:** Dual-session viewer (kitty claude + scrcpy on niri workspace "mopho"); keybind `Mod+Shift+V`. Not yet live-tested (deferred to preserve Phase 4 session).
- **Background monitor (baaryfqqj):** Polling `origin/phone` + `/health` every 40s; baselined @ `eca7716` (re-baselined after Phase 3 sign-off push 2026-07-18). Active. Will wake on next push (Phase 4 fix, Phase 5 start, or health drop).

## phoneAgentBuild Organization
- `design/` — architecture specs (phone-mcp-tool-schema.md, npu-pipeline-graph.md, trigger-propagation-model.md, offline-autonomy-model.md, deepseek-system-prompt.md)
- `phone/` — phases 0–7: PHONE-ENV.md, `prompts/phase-{0..7}-*.md`, `tools/{sensor,capture,ingest,pipeline}*.py`, `config/geofences.json`
- `laptop/` — phase 8 NixOS module work
- `DECISIONS.md` — D1–D14 (design constraints and known limitations)
- `build-plan.md` — eight-phase structure with commit templates
- `scripts/verify.sh` — pre-merge battery (expect 17 tools as of Phase 4)

## Relay (relay/)
- `relay/to-laptop/` — phone→laptop; Phase 1–4 delivery relays recorded
- `relay/to-phone/` — laptop→phone; Phase 1–3 closures recorded; Phase 3 sign-off pushed to origin 2026-07-18
- `relay/archive/` — closed threads
- Protocol: markdown + frontmatter `type: blocker|question|decision-request|handoff|fyi`, edited only by author

## Tailscale Mesh & Networking
- **volnix microVM:** Tailnet-joined via auto-key; exit-node active; 100.101.229.9:8462 reachable from laptop; meshes to phone over Tailscale
- **NixOS vms.nix edits:** Pending `make switch` deployment (autostart, exit-node, NAT, static route 100.64.0.0/10)
- **USB tether metric:** Deployed via NetworkManager settings (metric 700, WiFi 600) 2026-07-18; durable across reboots
