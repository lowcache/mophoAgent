---
type: todo
project: mophoAgent
last_updated: 2026-07-16
status: active
---

# Open Tasks

## Phone Build (Claude Code in proot-distro)
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
- [ ] Phone: phases 0–7 complete and tested; signal readiness via `relay/to-laptop/`
- [ ] Laptop: merge `phone` → `main` (fast-forward after phone push)
- [ ] Phone: rebase to `main` after integration
- [ ] Laptop: complete phase 8; merge `laptop` → `main`
- [ ] End-to-end test: MCP mesh between phone and laptop over Tailscale; voice, capture, processing, offline queue

## Stability & Proot Removal (prerequisites met 2026-07-16; deferred for priorities)
- [ ] Codify environment into versioned bootstrap.sh (install-time setup) + run.sh (launcher): UV_LINK_MODE=copy, ANDROID_API_LEVEL=24, PREFIX, patchelf, thread pins, termux-wake-lock. Launcher detects proot and fails fast with diagnostic.
- [ ] Native Termux legitimization: `pkg install llama-cpp python-numpy python-pillow python-onnxruntime`; retire ~/phone-agent-runtime hand-extracted .debs and LD_LIBRARY_PATH requirement.
- [ ] Convert phase-1 acceptance battery into repeatable `verify` skill: health 200, bearer auth 401, tools/list count, embedding dims, transcribe accuracy, OCR baseline.
- [ ] Research (tether): whether Claude Code + full build runs acceptably in native Termux (bionic) without proot userland; if viable, retire proot entirely.

## Infrastructure (outside mophoAgent scope)
- [ ] Commit vms.nix edits to ~/.nix-config (Tailscale guest auth + host IPMasquerade mesh fix) before rebuild to preserve config

## Known Deferred
- NPU via QNN SDK: blocked on llama.cpp QNN backend availability in Termux (revisit if mainline adds support)
- Programmatic unlock: intentionally out-of-scope per D7 (security and UX constraint)
- SSH phone↔laptop: design constraint per D3; not revisiting
