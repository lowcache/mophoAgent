---
type: todo
project: mophoAgent
last_updated: 2026-07-17
status: active
---

# Open Tasks

## Phone Build — Phase Core Tasks
- [x] Clone mophoAgent repo into proot-distro on Galaxy S26 Ultra
- [x] Spin up Claude Code; read phone/PHONE-ENV.md (build environment context)
- [x] Phase 0: MCP skeleton (FastMCP server, health/state/dispatch endpoints, systemd service) — verified 2026-07-15
- [x] Phase 1: NPU inference layer (whisper, OCR, embed, classify; CPU baseline) — committed 2026-07-16 @ da8849e; operator gate PASSED 2026-07-16; cross-tailnet sign-off 2026-07-16
- [x] Phase 2: Capture tools (audio, image, screenshot, share) — committed 2026-07-17 @ bf0f01f; verify.sh 5/5 PASS over tailnet
- [ ] Phase 2 operator gate: Install pkg ffmpeg+libsndfile; grant Termux:API permissions (mic, camera); test speech/VAD-trim, camera capture, screenshot (DISPLAY_OFF), Chrome share end-to-end; verify.sh rerun before Phase 3 start
- [ ] Phase 3: Processing pipelines (audio→text, image→ocr, share→extract)
- [ ] Phase 4: Sensor tools (IMU, modem, GPS, light, proximity)
- [ ] Phase 5: System tools (rish, exec, free_ram, notify)
- [ ] Phase 6: Voice AI + offline autonomy (persistent voice session, offline queue)
- [ ] Phase 7: Subconscious scheduler (event-driven task loop, priority queue, offline detection)
- [ ] Commit each phase per build-plan.md commit message template; push to `phone` branch only

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
