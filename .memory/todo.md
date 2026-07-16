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
- [ ] **PREREQUISITE for Phase 1:** Confirm native Termux `pkg install python uv` can build pydantic-core wheel on bionic. Phase 0 ran under proot; Phase 1+ requires native termux-api. Should be verified on device before Phase 1 starts.
- [ ] Phase 1: NPU inference layer (whisper, OCR, embed, classify; CPU baseline)
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
- [ ] Phone: phases 0–7 complete and tested; signal readiness via `relay/to-laptop/`
- [ ] Laptop: merge `phone` → `main` (fast-forward)
- [ ] Phone: rebase to `main`
- [ ] Laptop: complete phase 8; merge `laptop` → `main`
- [ ] End-to-end test: MCP mesh between phone and laptop over Tailscale; voice, capture, processing, offline queue

## Known Deferred
- NPU via QNN SDK: blocked on llama.cpp QNN backend availability in Termux (not a priority target; revisit if mainline adds support)
- Programmatic unlock: intentionally out-of-scope per D7 (security and UX constraint)
- SSH phone↔laptop: design constraint per D3; not revisiting
