---
type: todo
project: mophoAgent
last_updated: 2026-07-16
status: active
---

# Open Tasks

## Phone Build — Phase 2 Prep (stabilization, blocking prerequisites)
**Status:** P0–P3 implemented (72b04a1); P4 verify infrastructure staged; awaiting operator action to close gate and unblock Phase 2 core.

**Operator action (BLOCKING — required before Phase 2 resumes):**
- [ ] On phone (native Termux): Stop existing foreground server (lsof -ti:8462 | xargs -r kill -9), then run `phone-agent/scripts/bootstrap.sh` (starts runit service, waits for health 200)
- [ ] On this laptop: Add bearer token to ~/.config/phone-agent/token (64 hex chars from phone's ~/.config/phone-agent/token; keep out of transcripts)
- [ ] On this laptop: Run `phone-agent/scripts/verify.sh http://100.101.229.9:8462` (expected: 5/5 green — health 200, bearer-reject 401, 7-tool list, ping, 384-dim embed)
- [ ] **Gate closes** → relay status update → Phase 2 core tasks unblock

## Phone Build — Phase Core Tasks (after stabilization gate closes)
- [x] Clone mophoAgent repo into proot-distro on Galaxy S26 Ultra
- [x] Spin up Claude Code; read phone/PHONE-ENV.md (build environment context)
- [x] Phase 0: MCP skeleton (FastMCP server, health/state/dispatch endpoints, systemd service) — verified 2026-07-15
- [x] Phase 1: NPU inference layer (whisper, OCR, embed, classify; CPU baseline) — committed 2026-07-16 @ da8849e; operator gate PASSED 2026-07-16; laptop cross-tailnet sign-off verified 2026-07-16
- [ ] Phase 2: Capture tools (audio, image, screenshot, share)
- [ ] Phase 3: Processing pipelines (audio→text, image→ocr, share→extract)
- [ ] Phase 4: Sensor tools (IMU, modem, GPS, light, proximity)
- [ ] Phase 5: System tools (rish, exec, free_ram, notify)
- [ ] Phase 6: Voice AI + offline autonomy (persistent voice session, offline queue)
- [ ] Phase 7: Subconscious scheduler (event-driven task loop, priority queue, offline detection)
- [ ] Commit each phase per build-plan.md commit message template; push to `phone` branch only

## Laptop Build (Claude Code on laptop)
- [ ] Phase 8: NixOS module (mcp-gateway peer, proximity hooks, network routing, ingest-sync timer)

## Integration
- [ ] Phone: phases 2–7 complete and tested; signal readiness via `relay/to-laptop/`
- [ ] Laptop: merge `phone` → `main` (fast-forward after phone push)
- [ ] Phone: rebase to `main` after integration
- [ ] Laptop: complete phase 8; merge `laptop` → `main`
- [ ] End-to-end test: MCP mesh between phone and laptop over Tailscale; voice, capture, processing, offline queue

## Infrastructure (outside mophoAgent scope)
- [ ] Commit and apply vms.nix edits to ~/.nix-config (user added autostart=true for microvm@tailscale 2026-07-17; also add static route 100.64.0.0/10 to systemd.network.networks."11-tailscale-tap".routes for persistence across reboot)

## Known Deferred
- NPU via QNN SDK: blocked on llama.cpp QNN backend availability in Termux (revisit if mainline adds support)
- Programmatic unlock: intentionally out-of-scope per D7 (security and UX constraint)
- SSH phone↔laptop: design constraint per D3; not revisiting
