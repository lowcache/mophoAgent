---
type: todo
project: mophoAgent
last_updated: 2026-07-16
status: active
---

# Open Tasks

## Phone Build — Phase 2 Prep (stabilization, blocking prerequisites)
**Decision-request in relay/to-phone/20260716-0917-runtime-stabilization.md · awaiting response before phase 2 core tasks begin.**
- [ ] **P0 — Managed native service:** Implement `termux-services` (runit `sv`) + `Termux:Boot` + wake-lock so server survives proot/Claude session exit and Android lifecycle. Eliminates hand-run foreground fragility. Highest leverage.
- [ ] **P1 — Versioned bootstrap.sh + run.sh:** Codify LD_LIBRARY_PATH, thread pins (-t4 -tb4), patchelf, UV_LINK_MODE=copy, PREFIX, ANDROID_API_LEVEL, wake-lock contract. Fast-fail if run under proot, missing lib, or env var unset.
- [ ] **P2 — Enforce proot/native boundary:** Dev agent edits+commits from proot only; P0 service executes in native Termux. Never launch server or termux-api from proot.

## Phone Build — Phase Core Tasks (after P0–P2 complete)
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

## Post-Phase-2 Stabilization (P3–P4, deferred pending P0–P2 completion)
- [ ] **P3 — Native pkg install consolidation:** Retire ~/phone-agent-runtime hand-extracted .debs for native `pkg install llama-cpp python-numpy python-pillow python-onnxruntime`; document genuinely-missing fallbacks (onnxruntime/opencv) as single explicit stubs, not ad-hoc.
- [ ] **P4 — Pre-merge tailnet verify gate:** Convert phase-1 acceptance battery into repeatable `verify` skill (health 200, bearer 401, tools/list count, embedding dims, transcribe, OCR baseline); run from volnix against phone's tailnet IP before each phase merge. Mechanism that stops errors baking in.

## Infrastructure (outside mophoAgent scope)
- [ ] Commit vms.nix edits to ~/.nix-config (Tailscale guest auth + host IPMasquerade mesh fix) before rebuild to preserve config

## Known Deferred
- NPU via QNN SDK: blocked on llama.cpp QNN backend availability in Termux (revisit if mainline adds support)
- Programmatic unlock: intentionally out-of-scope per D7 (security and UX constraint)
- SSH phone↔laptop: design constraint per D3; not revisiting
