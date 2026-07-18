---
type: todo
project: mophoAgent
last_updated: 2026-07-18
status: active
---

# Open Tasks

## Phase 3 — CLOSED (2026-07-18)
- [x] Processing pipelines (audio→text, image→ocr, share→extract) — DELIVERED and verified 5/5 over tailnet
- [x] Verify tools/list count in verify.sh — RESOLVED (11→12; verify.sh updated in Phase 3)
- [x] Commit Phase 3 per build-plan.md template — DONE (3fac7e2)

## Phase 3 — Runtime Stabilization — PARTIALLY LIVE
- [x] **#1: Watchdog installation + verify** — DONE 2026-07-18. Operator ran `watchdog-install.sh` in native session; `termux-job-scheduler --pending` confirms job present (ID: 4623, discrepancy vs. relay-specified 462 noted in mistakes.md). Code: bootstrap.sh guard, watchdog.sh, watchdog-install.sh.
- [ ] **#2: Battery optimization exemption** — PENDING. Set Battery → Unrestricted for Termux + Termux:API (required for watchdog to survive idle kill). Not yet confirmed.
- [ ] **#3: Optional reboot confidence check** — PENDING (deferred until #2 confirmed).
- **Status:** Watchdog code in place; job installed; battery exemption blocks full activation. Idle-death defense not yet live without #2.

## Phase 4 — IN PROGRESS (2026-07-18)
- [ ] Sensor tools (IMU, modem, GPS, light, proximity) — locally committed @ fa9d214, not pushed yet
  - [x] Implement sensor_imu.py, sensor_modem.py, sensor_gps.py, sensor_light.py, sensor_proximity.py
  - [x] Geofence config (config/geofences.json)
  - [x] sensor_common.py (shared utilities)
  - [ ] Delivery relay to laptop (in progress)
  - [ ] Tag commit per build-plan.md template
  - [ ] Push to `phone` branch
- [ ] Operator gate: on-device sensor tool verification (pending delivery relay)
- [ ] Commit Phase 4 per build-plan.md commit message template

## Phase 4 — Core Tasks (continuation)
- [ ] Phase 5: System tools (rish, exec, free_ram, notify)
- [ ] Phase 6: Voice AI + offline autonomy (persistent voice session, offline queue)
- [ ] Phase 7: Subconscious scheduler (event-driven task loop, priority queue, offline detection)
- [ ] Commit each phase per build-plan.md template; push to `phone` branch only

## Dual-Session Viewer & Monitoring (2026-07-18)
- [ ] **Dual-session viewer live test:** Press `Mod+Shift+V` to launch mopho workspace (kitty claude + scrcpy side-by-side). Verify layout, keybind resolution, both panes functional. Deferred until current scrcpy session complete (Phase 4 in progress).
- [x] **Agent monitoring channel verified:** mopho-watch deployed, one-frame proof captured and Read back. Continuous loop (2s cadence) ready on-demand. Passive-and-advise strategy active.
- [x] **Background watcher deployed:** bgbj2xnwk polling `origin/phone` + `/health` every 40s; will wake on Phase 4 push or health drop.

## Integration
- [ ] Phone: phases 3–7 complete and tested; signal readiness via `relay/to-laptop/`
  - [x] Phase 3 readiness signaled; sign-off committed locally (c440d34), awaiting Phase 4 push before landing
  - [ ] Phase 4 push imminent (relay in progress)
  - [ ] Phase 5–7 to follow
- [ ] Laptop: merge `phone` → `main` (fast-forward after phone push)
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
