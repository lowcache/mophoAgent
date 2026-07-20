---
type: todo
project: mophoAgent
last_updated: 2026-07-19
status: active
---

# Open Tasks

## Phase 3 — CLOSED (2026-07-18)
- [x] Processing pipelines (audio→text, image→ocr, share→extract) — DELIVERED and verified 5/5 over tailnet
- [x] Verify tools/list count in verify.sh — RESOLVED (11→12; verify.sh updated in Phase 3)
- [x] Commit Phase 3 per build-plan.md template — DONE (3fac7e2)

## Phase 3 — Runtime Stabilization — FULLY CLOSED (2026-07-18)
- [x] **#1: Watchdog installation + verify** — DONE 2026-07-18. Operator ran `watchdog-install.sh` in native session; `termux-job-scheduler --pending` confirms job 462 present. ✅ CONFIRMED
- [x] **#2: Battery optimization exemption** — DONE 2026-07-18. Termux + Termux:API set to Battery → Unrestricted. ✅ CONFIRMED
- [ ] **#3: Optional reboot confidence check** — DEFERRED (Termux:Boot → /health 200 → shared-URL lands in processed/summaries). Nice-to-have, not blocking.
- **Status:** ✅ **CRITICAL idle-death defense fully active.** Watchdog job 462 pending; battery exemption confirmed; phantom-process-killer mitigation in force.

## Phase 4 — IN PROGRESS (2026-07-18/2026-07-19)
- [x] Sensor tools (IMU, modem, GPS, light, proximity) — **DELIVERED and DEPLOYED LIVE (17 tools)**
  - [x] Implement sensor_imu.py, sensor_modem.py, sensor_gps.py, sensor_light.py, sensor_proximity.py
  - [x] Geofence config (config/geofences.json)
  - [x] sensor_common.py (shared utilities)
  - [x] Delivery relay to laptop (2026-07-18)
  - [x] Tag commit phone-mcp-phase-4
  - [x] Push to `phone` branch (2026-07-18)
  - [x] Deploy to native runtime (2026-07-18); runit restart clean, no idle-death repeat
  - [x] Verify live: `/health` 200, verify.sh 5/5 @ 17 tools (2026-07-18)
  - [x] **Fix bugs found in on-device sensor validation (2026-07-18, fixed 2026-07-19)**
    - [x] Proximity: substring "proximity" matched "Touch Proximity Sensor" (virtual) instead of physical IR sensor; fixed: `_ROLE_EXCLUDE` filter + sensor list persistence (commit 17c239d)
    - [x] Modem network_type: constant 18 (IWLAN) not in string map; fixed: `NUMERIC_CELL_TYPES` map extended with comprehensive Android constants (commit 17c239d)
  - [x] Phone: push fix commits to origin/phone (2026-07-19: e8f2487 relay, 17c239d sensor fixes)
  - [ ] Laptop: deploy fixes to native runtime (awaiting verify.sh green)
  - [ ] Laptop: re-run verify.sh (READY; blocked on auth token only)
  - [ ] Phase 4 sign-off relay (pending verify.sh 5/5 + on-device acceptance reads green)
- [ ] Operator gate: on-device sensor reads verification
  - [x] Termux:API Sensors + Location permissions — GRANTED
  - [ ] Live reads go green (desk→on_desk, walk→walking, modem SSID/signal, gps, light, proximity) — IN PROGRESS, pending fix re-test (fixes deployed 2026-07-19)
- **Status:** Fixes pushed; endpoint HTTP 200 reachable; laptop verify.sh ready (auth token only blocker); on-device re-test pending.

## Phase 5–7 (not yet started)
- [ ] Phase 5: System tools (rish, exec, free_ram, notify)
- [ ] Phase 6: Voice AI + offline autonomy (persistent voice session, offline queue)
- [ ] Phase 7: Subconscious scheduler (event-driven task loop, priority queue, offline detection)
- [ ] Commit each phase per build-plan.md template; push to `phone` branch only

## Dual-Session Viewer & Monitoring (2026-07-18)
- [ ] **Dual-session viewer live test:** Press `Mod+Shift+V` to launch mopho workspace (kitty claude + scrcpy side-by-side). Verify layout, keybind resolution, both panes functional. Deferred until Phase 4 sensor validation complete.
- [x] **Agent monitoring channel verified:** mopho-watch deployed, one-frame proof captured and Read back. Continuous loop (2s cadence) ready on-demand. Passive-and-advise strategy active.
- [x] **Background watcher deployed:** baaryfqqj polling `origin/phone` + `/health` every 40s; baselined @ `eca7716` (re-baselined after Phase 3 sign-off push 2026-07-18). Active; will wake on next push or health drop.

## Integration
- [x] Phone: Phase 3 complete, tested, signed off, and pushed to origin/phone @ eca7716
  - [x] Phase 3 readiness signaled via relay; sign-off pushed (eca7716)
  - [ ] Phase 4 sign-off (awaiting verify.sh 5/5 execution)
  - [ ] Phase 5–7 to follow
- [ ] Laptop: merge `phone` → `main` (fast-forward after Phase 4 sign-off)
- [ ] Phone: rebase to `main` after integration
- [ ] Laptop: complete phase 8; merge `laptop` → `main`
- [ ] End-to-end test: MCP mesh between phone and laptop over Tailscale; voice, capture, processing, offline queue

## Infrastructure (outside mophoAgent scope)
- [ ] Apply vms.nix to system via `make switch` in ~/.nix-config (edits: tailscale autostart, exit-node, NAT, static route; syntax-checked valid, pending deployment)

## Known Deferred
- NPU via QNN SDK: blocked on llama.cpp QNN backend availability in Termux (revisit if mainline adds support)
- Programmatic unlock: intentionally out-of-scope per D7 (security and UX constraint)
- SSH phone↔laptop: design constraint per D3; not revisiting
- True laptop-terminal attach to phone session: blocked by D3 (would require tailnet tmux socket, violates no-SSH stance)
