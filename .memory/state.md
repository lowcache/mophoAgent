---
type: state
project: mophoAgent
last_updated: 2026-07-16
status: active
---

# System State

## Repository Structure
- **Branches:** `main` (integration base), `phone` (phases 0–7), `laptop` (phase 8)
- **Branch ownership:** claude-phone owns `phone` branch; claude-laptop owns `laptop` branch (phase 8) and all integration merges
- **Latest commits:** `origin/phone` @ `c6c8b7b` (probe tailnet bind address, 2026-07-17); `laptop` @ ce840a2; `main` @ fdbe9a7
- **Phase 1 status:** CLOSED (delivery @ da8849e, operator gate PASSED 2026-07-16, cross-tailnet sign-off verified 2026-07-16)
- **Phase 2 prep:** Stabilization (P0–P4) implementation committed 72b04a1; verification infrastructure staged; awaiting operator action (bearer token + verify.sh battery run)

## phoneAgentBuild Organization
- `design/` — architecture specs: phone-mcp-tool-schema.md, npu-pipeline-graph.md, trigger-propagation-model.md, offline-autonomy-model.md, deepseek-system-prompt.md
- `phone/` — phases 0–7: PHONE-ENV.md, `prompts/phase-{0..7}-*.md`
- `laptop/` — phase 8 prompt and integration work
- `DECISIONS.md` — authoritative D1–D11 (design constraints override prompts/design/)
- `build-plan.md` — eight-phase structure with commit templates

## Relay (relay/)
- `relay/to-laptop/` — phone→laptop messages; Phase 1 gate results (20260716-gate-results.md); Phase 2 status report (20260717-runtime-stabilization-done.md)
- `relay/to-phone/` — laptop→phone messages; Phase 1 sign-off (20260716-0751-phase1-signoff.md) **CLOSED**; stabilization decision-request (20260716-0917-runtime-stabilization.md) **ANSWERED** (report 20260717)
- `relay/archive/` — closed threads
- Protocol: markdown + frontmatter `type: blocker|question|decision-request|handoff|fyi`, edited only by author

## Phase 1 Closure (2026-07-16) — COMPLETE
- **Delivery:** NPU inference (whisper, OCR, embed, classify; CPU baseline D5; priority queue D8) @ da8849e
- **On-device gate:** Native Termux launch Galaxy S26; all acceptance criteria PASS (commit 3827698)
- **Cross-tailnet sign-off:** `GET http://100.101.229.9:8462/health` → 200 `{"status":"ok"}` from laptop over Tailscale (cellular RTT ~357ms); auth boundary (`/mcp` bad bearer) → 401
- **Closure:** Relay flipped to status=closed; pushed origin/phone @ 6a11801 (2026-07-16)
- **Incident:** Phone MCP server died after gate; relaunch restored /health 200. Not a persistent managed process — permanent fix (managed service + bootstrap.sh) is stabilization P0 (committed 72b04a1)

## Phase 2 Preparation (2026-07-17, in progress)
- **P0–P3 committed (72b04a1):** Managed service (termux-services runit + Termux:Boot + wake-lock); bootstrap.sh codification (LD_LIBRARY_PATH, thread pins, PREFIX, patchelf, UV_LINK_MODE, ANDROID_API_LEVEL, wake-lock contract); proot/native boundary enforcement (D11); native pkg install consolidation (pkg install fallback stubs)
- **P4 verify infrastructure staged (2026-07-17):**
  - verify.sh ready at phone-agent/scripts/verify.sh (battery: health 200, bearer-reject 401, 7-tool list, ping, 384-dim embed)
  - Bearer token infrastructure: ~/.config/phone-agent/token (dir mode 700, file created, awaiting secret from phone)
  - Tailnet path confirmed: `GET http://100.101.229.9:8462/health` → 200 from volnix (2026-07-17 16:45 UTC)
- **VM and routing (user applied 2026-07-17):**
  - microvm@tailscale: active (started), autostart flag enabled in vms.nix (pending make switch application)
  - Route 100.64.0.0/10 via 192.168.101.2: active in routing table (manual ip route command; not yet persistent in vms.nix systemd.network)
- **Operator action (blocking):** (1) Stop existing :8462 foreground process on phone; (2) Run phone-agent/scripts/bootstrap.sh in native Termux (starts runit service, waits health 200); (3) Place bearer token (64 hex) at ~/.config/phone-agent/token from phone's ~/.config/phone-agent/token; (4) Run phone-agent/scripts/verify.sh http://100.101.229.9:8462 from volnix (expected 5/5 green → closes stabilization gate, unblocks Phase 2 core)

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
  - Host: `networks."11-tailscale-tap".networkConfig.IPMasquerade="both"` ← **CRITICAL FIX (2026-07-16):** enables guest internet to reach Tailscale coordination server
- **Networking:** vm-tailscale tap 192.168.101.1/24 ↔ guest 192.168.101.2/24; virtiofs /var/lib/tailscale; host route 100.64.0.0/10 via 192.168.101.2 (active via manual command; static declaration still missing from vms.nix)
- **Artifact status:** vms.nix edits working via active `make switch` build; **autostart flag added 2026-07-17, route still manual** — recommend commit both before next rebuild
