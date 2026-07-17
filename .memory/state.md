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
- **Latest commits:** `origin/phone` @ `b702c28` (phase 2 closure 2026-07-17); `laptop` @ ce840a2; `main` @ fdbe9a7
- **Phase 1 status:** CLOSED (delivery @ da8849e, operator gate PASSED 2026-07-16, cross-tailnet sign-off verified 2026-07-16)
- **Phase 2 status:** CLOSED (operator gate PASSED on-device 2026-07-17, bf0f01f; laptop cross-tailnet verify.sh 5/5 PASS 2026-07-17; sign-off committed 2026-07-17)
- **Phase 3 status:** IN PROGRESS (operator gave go 2026-07-17)

## phoneAgentBuild Organization
- `design/` — architecture specs: phone-mcp-tool-schema.md, npu-pipeline-graph.md, trigger-propagation-model.md, offline-autonomy-model.md, deepseek-system-prompt.md
- `phone/` — phases 0–7: PHONE-ENV.md, `prompts/phase-{0..7}-*.md`
- `laptop/` — phase 8 prompt and integration work
- `DECISIONS.md` — authoritative D1–D11 (design constraints override prompts/design/)
- `build-plan.md` — eight-phase structure with commit templates

## Relay (relay/)
- `relay/to-laptop/` — phone→laptop messages; Phase 1 gate results (20260716-gate-results.md); Phase 2 sign-off (20260717-phase2-signoff.md) **CLOSED**
- `relay/to-phone/` — laptop→phone messages; Phase 1 sign-off (20260716-0751-phase1-signoff.md) **CLOSED**; stabilization decision (20260716-0917-runtime-stabilization.md) **CLOSED**
- `relay/archive/` — closed threads
- Protocol: markdown + frontmatter `type: blocker|question|decision-request|handoff|fyi`, edited only by author

## Phase 2 Closure (2026-07-17) — COMPLETE
- **Delivery:** Capture tools (audio, image, screenshot, share) @ bf0f01f
- **On-device operator gate:** Speech/VAD-trim, camera capture, screenshot (DISPLAY_OFF), browser share end-to-end — ALL PASS (2026-07-17)
- **Cross-tailnet verification:** Laptop independently re-ran verify.sh (2026-07-17) → 5/5 PASS; /health 200, bad bearer 401, tools/list expected count, ping, embed (384-dim, norm ~1.0)
- **Capture tools (4):** `phone.capture.{audio,image,screenshot,share}`
  - Audio: m4a via termux-microphone-record → ffmpeg transcode to WAV (stdlib wave I/O; soundfile removed)
  - Image: Android camera via rish (Shizuku bridge); requires Termux:API + camera permission
  - Screenshot: framebuffer dump via Termux:API (DISPLAY_OFF)
  - Share: Browser share hooks auto-installed to ~/bin (marker-guarded); supports Brave, Chrome, and any share-capable browser
- **VAD:** Silero v5 onnxruntime (lazy singleton `vad/gate.py`). Model: src/silero_vad/data/silero_vad.onnx (2.3 MB). Input shape [2,b,128]/sr verified.
- **Ingest layer:** Queue directory `phone-agent/delivering/` with persistent retry_count (JSON per task); tools `phone.ingest.{list,fetch}`
- **Dependencies:** ffmpeg only (libsndfile dropped; stdlib wave I/O used instead). Termux:API permissions required (mic, camera).
- **Closure:** Relay sign-off committed; pushed origin/phone @ b702c28 (2026-07-17)
- **Incident (2026-07-17, ~16:34 UTC):** Native runit supervision tree died after 12h+ idle gap. All procs (uvicorn :8462, llama :8463/:8464, whisper :8465, sshd :8022, runsv/runsvdir) offline; supervise/pid stale since 04:14. Recovery: operator-only (native Termux session auto-starts runsvdir via termux-services profile.d, or run scripts/bootstrap.sh; then `sv up phone-agent`). Suspected phantom-process-killer or OS background app kill (proot session survived, not device reboot). Phase 3 action: runit watchdog + battery-optimization exemption + external health check.

## Phase 1 MCP Runtime (for reference; managed service in progress)
- **Server:** Native Termux runit service via termux-services (pending bootstrap.sh codification)
- **Build:** ~/phone-agent-runtime (hand-extracted .debs: llama-server, whisper, onnxruntime, numpy, PIL); native Termux venv exists
- **Known gaps:** Watchdog for idle-death scenarios (Phase 3 action item)

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
