---
type: todo
project: mophoAgent
last_updated: 2026-07-17
status: active
---

# Open Tasks

## Phase 3 — PRIORITY: Runtime Stabilization
- [ ] **CRITICAL: Runit watchdog + health check** — Address 2026-07-17 incident (idle-death after 12h+). Implement: (a) battery-optimization exemption for phone-agent service, (b) raise `max_phantom_processes` at bootstrap, (c) external health-check via termux-job-scheduler polling `/health` endpoint. Incident analysis suggests phantom-process-killer or OS app-kill; watchdog prevents silent failures.
- [ ] Verify tools/list count in verify.sh — Phase 2 closed @ 11 tools; Phase 3 spec asserts 12 tools (audio→text, image→ocr, share→extract). Confirm discrepancy and update verify.sh accordingly before Phase 3 verify gate.
- [ ] Processing pipelines (audio→text, image→ocr, share→extract) — currently in progress on phone agent as of 2026-07-18.
- [ ] Commit Phase 3 per build-plan.md template

## Phase 3 — Core Tasks (continuation)
- [ ] Phase 4: Sensor tools (IMU, modem, GPS, light, proximity)
- [ ] Phase 5: System tools (rish, exec, free_ram, notify)
- [ ] Phase 6: Voice AI + offline autonomy (persistent voice session, offline queue)
- [ ] Phase 7: Subconscious scheduler (event-driven task loop, priority queue, offline detection)
- [ ] Commit each phase per build-plan.md commit message template; push to `phone` branch only

## Dual-Session Viewer & Monitoring (2026-07-18)
- [ ] **Dual-session viewer live test:** Press `Mod+Shift+V` to launch mopho workspace (kitty claude + scrcpy side-by-side). Verify layout, keybind resolution, and both panes functional. Defer until current scrcpy session complete.
- [ ] **Agent monitoring channel verified:** mopho-watch deployed, one-frame proof captured and Read back. Continuous loop (2s cadence) ready on-demand. Passive-and-advise strategy active.
- [ ] Record dual-session viewer delivery in `.memory/` against "ADB live monitoring infrastructure" todo (partially delivered; full ADB session attach remains blocked by D3 constraint).

## Laptop Build (Claude Code on laptop)
- [ ] Phase 8: NixOS module (mcp-gateway peer, proximity hooks, network routing, ingest-sync timer)

## Integration
- [ ] Phone: phases 3–7 complete and tested; signal readiness via `relay/to-laptop/`
- [ ] Laptop: merge `phone` → `main` (fast-forward after phone push)
- [ ] Phone: rebase to `main` after integration
- [ ] Laptop: complete phase 8; merge `laptop` → `main`
- [ ] End-to-end test: MCP mesh between phone and laptop over Tailscale; voice, capture, processing, offline queue

## Infrastructure (outside mophoAgent scope)
- [ ] Apply vms.nix to system via `make switch` in ~/.nix-config (autostart flag for microvm@tailscale + static route 100.64.0.0/10 edited 2026-07-16; syntax-checked valid; pending deployment)

## Known Deferred
- NPU via QNN SDK: blocked on llama.cpp QNN backend availability in Termux (revisit if mainline adds support)
- Programmatic unlock: intentionally out-of-scope per D7 (security and UX constraint)
- SSH phone↔laptop: design constraint per D3; not revisiting
- True laptop-terminal attach to phone session: blocked by D3 (would require tailnet tmux socket, violates no-SSH stance)
