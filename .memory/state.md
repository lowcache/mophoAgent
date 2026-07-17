---
type: state
project: mophoAgent
last_updated: 2026-07-17
status: active
---

# System State

## Repository Structure
- **Branches:** `main` (integration base), `phone` (phases 0–7), `laptop` (phase 8)
- **Branch ownership:** claude-phone owns `phone` branch; claude-laptop owns `laptop` branch (phase 8) and all integration merges
- **Latest commits:** `origin/phone` @ `d94e7da` (relay: phase 2 delivery 2026-07-17); `laptop` @ ce840a2; `main` @ fdbe9a7
- **Phase 1 status:** CLOSED (delivery @ da8849e, operator gate PASSED 2026-07-16, cross-tailnet sign-off verified 2026-07-16)
- **Phase 2 status:** DELIVERED (bf0f01f @ 2026-07-17); capture tools live; verify.sh battery 5/5 PASS over tailnet (2026-07-17); operator gate pending

## phoneAgentBuild Organization
- `design/` — architecture specs: phone-mcp-tool-schema.md, npu-pipeline-graph.md, trigger-propagation-model.md, offline-autonomy-model.md, deepseek-system-prompt.md
- `phone/` — phases 0–7: PHONE-ENV.md, `prompts/phase-{0..7}-*.md`
- `laptop/` — phase 8 prompt and integration work
- `DECISIONS.md` — authoritative D1–D11 (design constraints override prompts/design/)
- `build-plan.md` — eight-phase structure with commit templates

## Relay (relay/)
- `relay/to-laptop/` — phone→laptop messages; Phase 1 gate results (20260716-gate-results.md); Phase 2 delivery (20260717-phase2-delivery.md, type: fyi, status: open)
- `relay/to-phone/` — laptop→phone messages; Phase 1 sign-off (20260716-0751-phase1-signoff.md) **CLOSED**; stabilization decision (20260716-0917-runtime-stabilization.md) **CLOSED**
- `relay/archive/` — closed threads
- Protocol: markdown + frontmatter `type: blocker|question|decision-request|handoff|fyi`, edited only by author

## Phase 1 Closure (2026-07-16) — COMPLETE
- **Delivery:** NPU inference (whisper, OCR, embed, classify; CPU baseline D5; priority queue D8) @ da8849e
- **On-device gate:** Native Termux launch Galaxy S26; all acceptance criteria PASS (commit 3827698)
- **Cross-tailnet sign-off:** `GET http://100.101.229.9:8462/health` → 200 from laptop over Tailscale (cellular RTT ~357ms); auth boundary (`/mcp` bad bearer) → 401
- **Closure:** Relay flipped to status=closed; pushed origin/phone @ 6a11801 (2026-07-16)
- **Incident:** Phone MCP server died after gate; relaunch restored /health 200. Permanent fix (managed service + bootstrap.sh) is stabilization P0 (committed 72b04a1)

## Phase 2 Delivery (2026-07-17) — COMPLETE & VERIFIED
- **Commit:** bf0f01f; tag `phone-mcp-phase-2`
- **Capture tools (4):** `phone.capture.{audio,image,screenshot,share}`
  - Audio: m4a via termux-microphone-record → ffmpeg transcode to WAV
  - Image: Android camera via rish (Shizuku bridge); requires Termux:API + camera permission
  - Screenshot: framebuffer dump via Termux:API (DISPLAY_OFF)
  - Share: Chrome/system share hooks auto-installed to ~/bin (marker-guarded)
- **VAD:** Silero v5 onnxruntime (lazy singleton `vad/gate.py`). Model: src/silero_vad/data/silero_vad.onnx (2.3 MB). Input shape [2,b,128]/sr verified.
- **Ingest layer:** Queue directory `phone-agent/delivering/` with persistent retry_count (JSON per task); tools `phone.ingest.{list,fetch}`
- **Deploy pattern (validated):** proot commit → native `git fetch /root/mophoAgent phone && merge --ff-only` → TERM server pid → runit respawn. core.createObject=rename intact; works cleanly.
- **Verification:** 11 tools total; verify.sh 5/5 PASS over tailnet from laptop (2026-07-17)
  - PASS: /health 200, bad bearer 401, tools/list expected count, ping, embed (384-dim, norm ~1.0)
- **Operator gate pending:** Install pkg ffmpeg+libsndfile; grant Termux:API permissions (mic, camera); test speech/VAD-trim, camera capture, screenshot (DISPLAY_OFF), Chrome share end-to-end; verify.sh rerun before Phase 3 start

## Phase 1 MCP Runtime (for reference; will be replaced by managed service on P0 completion)
- **Server:** Hand-run foreground (termux-wake-lock; cd ~/phone-agent; LD_LIBRARY_PATH=$HOME/phone-agent-runtime/lib .venv/bin/python main.py); not persistent/managed
- **Build:** ~/phone-agent-runtime (hand-extracted .debs: llama-server, whisper, onnxruntime, numpy, PIL); native Termux venv exists
- **Known gaps:** No systemd service; no launcher/bootstrap codification; no repeatable acceptance battery skill for regression testing

## Tailscale Mesh (volnix VM, active as of 2026-07-17)
- **Status:** VM joined tailnet via auto-key auth; exit-node active; online in admin console; mesh connectivity to phone verified (100.101.229.9:8462 answers on tailnet)
- **Config applied in ~/.nix-config/nixos/vms.nix (via `make switch`, pending):**
  - Guest: `services.tailscale.authKeyFile=/var/lib/tailscale/authkey` (auto-join reusable key)
  - Guest: `services.tailscale.extraUpFlags=["--advertise-exit-node"]`
  - Guest: `services.tailscale.enable=true` (autostart enabled 2026-07-17, pending make switch)
  - Guest: `networking.nat` masquerade (SNAT via tailscale0)
  - Host: `networks."11-tailscale-tap".networkConfig.IPMasquerade="both"` (enables guest internet to Tailscale coordination)
- **Networking:** vm-tailscale tap 192.168.101.1/24 ↔ guest 192.168.101.2/24; virtiofs /var/lib/tailscale; host route 100.64.0.0/10 via 192.168.101.2
- **Artifact status:** vms.nix edits complete; syntax-checked valid; pending `make switch` deployment
