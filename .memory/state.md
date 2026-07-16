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
- **Latest commits:** `origin/phone` @ `326decb` (stabilization plan decision-request + memory note, 2026-07-16); `laptop` @ ce840a2; `main` @ fdbe9a7
- **Phase 1 status:** CLOSED (delivery @ da8849e, operator gate PASSED 2026-07-16, cross-tailnet sign-off verified 2026-07-16)
- **Phase 2 prep:** Stabilization plan (P0–P2) decision-request filed 2026-07-16 in relay/to-phone/20260716-0917-runtime-stabilization.md; awaiting claude-phone response

## phoneAgentBuild Organization
- `design/` — architecture specs: phone-mcp-tool-schema.md, npu-pipeline-graph.md, trigger-propagation-model.md, offline-autonomy-model.md, deepseek-system-prompt.md
- `phone/` — phases 0–7: PHONE-ENV.md, `prompts/phase-{0..7}-*.md`
- `laptop/` — phase 8 prompt and integration work
- `DECISIONS.md` — authoritative D1–D10 (design constraints override prompts/design/)
- `build-plan.md` — eight-phase structure with commit templates

## Relay (relay/)
- `relay/to-laptop/` — phone→laptop messages; Phase 1 gate results (20260716-gate-results.md)
- `relay/to-phone/` — laptop→phone messages; Phase 1 sign-off (20260716-0751-phase1-signoff.md) **CLOSED**; stabilization plan (20260716-0917-runtime-stabilization.md) **OPEN** (decision-request, P0–P4 before phases 2–7)
- `relay/archive/` — closed threads
- Protocol: markdown + frontmatter `type: blocker|question|decision-request|handoff|fyi`, edited only by author

## Phase 1 Closure (2026-07-16)
- **Delivery:** NPU inference (whisper, OCR, embed, classify; CPU baseline D5; priority queue D8) @ da8849e
- **On-device gate:** Native Termux launch Galaxy S26; all acceptance criteria PASS (commit 3827698)
- **Cross-tailnet sign-off:** `GET http://100.101.229.9:8462/health` → 200 `{"status":"ok"}` from laptop over Tailscale (cellular RTT ~357ms); auth boundary (`/mcp` bad bearer) → 401
- **Closure:** Relay flipped to status=closed; pushed origin/phone @ 6a11801 (2026-07-16)
- **Incident:** Phone MCP server died after gate; relaunch restored /health 200. Not a persistent managed process — permanent fix (managed service + bootstrap.sh) now priority P0 (filed 2026-07-16)

## Tailscale Mesh (volnix VM, online 2026-07-16)
- **Status:** VM joined tailnet via auto-key auth; exit-node active; online in admin console; mesh connectivity to phone verified
- **Config applied (in ~/.nix-config/nixos/vms.nix, via `make switch`):**
  - Guest: `services.tailscale.authKeyFile=/var/lib/tailscale/authkey` (auto-join reusable key)
  - Guest: `services.tailscale.extraUpFlags=["--advertise-exit-node"]`
  - Guest: `networking.nat` masquerade (SNAT via tailscale0)
  - Host: `networks."11-tailscale-tap".networkConfig.IPMasquerade="both"` ← **CRITICAL FIX (2026-07-16):** enables guest internet to reach Tailscale coordination server; was missing, caused auth timeout
- **Networking:** vm-tailscale tap 192.168.101.1/24 ↔ guest 192.168.101.2/24; virtiofs /var/lib/tailscale; host route 100.64.0.0/10 via 192.168.101.2
- **Artifact status:** vms.nix edits working via active `make switch` build; **UNCOMMITTED in ~/.nix-config** — recommend commit before rebuild

## Phase 1 MCP Runtime
- **Server:** Hand-run foreground (termux-wake-lock; cd ~/phone-agent; LD_LIBRARY_PATH=$HOME/phone-agent-runtime/lib .venv/bin/python main.py); not persistent/managed
- **Build:** ~/phone-agent-runtime (hand-extracted .debs: llama-server, whisper, onnxruntime, numpy, PIL); native Termux venv exists
- **Known gaps:** No systemd service; no launcher/bootstrap codification; no repeatable acceptance battery skill for regression testing
- **Stability plan:** Core insight is boundary separation (proot=dev only; native Termux=runtime+device I/O). P0 (managed service via termux-services runit + Termux:Boot + wake-lock) eliminates hand-run fragility and blocks phase 2
