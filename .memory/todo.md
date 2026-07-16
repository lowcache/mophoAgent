---
type: todo
project: mophoAgent
last_updated: 2026-07-15
status: active
---

# Open Tasks

## Phone Build (Claude Code in proot-distro)
- [x] Clone mophoAgent repo into proot-distro on Galaxy S26 Ultra
- [x] Spin up Claude Code; read phone/PHONE-ENV.md (build environment context)
- [x] Phase 0: MCP skeleton (FastMCP server, health/state/dispatch endpoints, systemd service) — verified 2026-07-15
- [x] Phase 1: NPU inference layer (whisper, OCR, embed, classify; CPU baseline) — committed 2026-07-16 @ da8849e; relay handoff @ b83ca19
- [BLOCKED] **Operator gate before Phase 2:** Native Termux launch validation. Restart live server with `LD_LIBRARY_PATH=$HOME/phone-agent-runtime/lib` + `termux-wake-lock`; verify termux-api access with deployed phase-1 code. Battery and deviation results in relay @ b83ca19.
- [ ] Phase 2: Capture tools (audio, image, screenshot, share)
- [ ] Phase 3: Processing pipelines (audio→text, image→ocr, share→extract)
- [ ] Phase 4: Sensor tools (IMU, modem, GPS, light, proximity)
- [ ] Phase 5: System tools (rish, exec, free_ram, notify)
- [ ] Phase 6: Voice AI + offline autonomy (persistent voice session, offline queue)
- [ ] Phase 7: Subconscious scheduler (event-driven task loop, priority queue, offline detection)
- [ ] Commit each phase per build-plan.md commit message template; push to `phone` branch only

## Laptop Build (Claude Code on laptop)
- [ ] Phase 8: NixOS module (mcp-gateway peer, proximity hooks, network routing, ingest-sync timer)
- [REBASE QUEUED] Doc fix (phase-1-npu-inference.md: models root per D2); rebasing onto origin/phone @ b83ca19 then pushing

## Integration
- [ ] Phone: phases 0–7 complete and tested; signal readiness via `relay/to-laptop/`
- [ ] Laptop: merge `phone` → `main` (fast-forward after phone push)
- [ ] Phone: rebase to `main` after integration
- [ ] Laptop: complete phase 8; merge `laptop` → `main`
- [ ] End-to-end test: MCP mesh between phone and laptop over Tailscale; voice, capture, processing, offline queue

## Known Deferred
- NPU via QNN SDK: blocked on llama.cpp QNN backend availability in Termux (revisit if mainline adds support)
- Programmatic unlock: intentionally out-of-scope per D7 (security and UX constraint)
- SSH phone↔laptop: design constraint per D3; not revisiting
