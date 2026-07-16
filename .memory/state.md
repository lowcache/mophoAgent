---
type: state
project: mophoAgent
last_updated: 2026-07-16
status: active
---

# System State

## Repository Structure
- **Branches:** `main` (integration base), `phone` (phases 0–7), `laptop` (phase 8)
- **Branch ownership:** claude-phone owns `phone` branch (phases 0–7); claude-laptop owns `laptop` branch (phase 8) and performs integration merges. Main is integration-only.
- **Latest commits:** `origin/phone` @ `25bf2ff` (laptop sign-off pushed 2026-07-16); `laptop` @ ce840a2; `main` @ fdbe9a7
- **Integration status:** Phase 1 delivered (da8849e) + operator gate PASSED (3827698, on-device all criteria met) + laptop sign-off (25bf2ff). Phase 2 ready to start. Tailnet /health check (sign-off closure prerequisite) in progress.

## phoneAgentBuild Organization
- `design/` — architecture specifications: phone-mcp-tool-schema.md, npu-pipeline-graph.md, trigger-propagation-model.md, offline-autonomy-model.md, deepseek-system-prompt.md
- `phone/` — phases 0–7: PHONE-ENV.md (build context), `prompts/phase-{0..7}-*.md`
- `laptop/` — phase 8 prompt and integration work
- `DECISIONS.md` — authoritative D1–D10 (overrides contradictions in design/ and prompts/)
- `build-plan.md` — eight-phase structure with commit templates

## Relay Dropbox (relay/)
- `relay/to-laptop/` — messages from claude-phone to claude-laptop; Phase 1 gate results (20260716-gate-results.md) all on-device criteria PASS
- `relay/to-phone/` — messages from claude-laptop to claude-phone; Phase 1 sign-off (20260716-0751-phase1-signoff.md) written, status=open pending tailnet /health
- `relay/archive/` — closed message threads (phase-0-signoff moved here 2026-07-15)
- Message protocol: markdown files on author's branch; frontmatter `type: blocker|question|decision-request|handoff|fyi`

## Phase 1 Operator Gate Results (2026-07-16)
- **Gate run:** Native Termux launch validation on Galaxy S26
- **On-device acceptance battery (ALL PASS):** native launch (pid 8467, no proot in ancestry), `/health` 200, bad bearer 401, `tools/list`=7 (embed + whisper backends), live embed 384-dim/unit-norm/66ms latency, `termux-battery-status` valid JSON
- **Q1 (path conflict):** `~/phone-agent` is symlink to `~/mophoAgent/phone-agent`, no conflict
- **Q2 (branch reconciliation):** `npu-inference-layer-phase1` was session title, not branch; all work on `phone` branch
- **Laptop reconciliation:** Local memory commit (ce840a2) rebased onto gate-pass (3827698 → 148efac); pushed to origin/phone (25bf2ff)
- **Laptop sign-off:** relay/to-phone/20260716-0751-phase1-signoff.md (status=open); all on-device criteria accepted, one item pending: tailnet `/health` check from volnix over Tailscale

## Tailscale VM Bringup (in progress)
- **Context:** Mesh node never stood up on volnix. `tailscale` microvm has `autostart = false`, currently inactive. Required for Phase 1 sign-off closure and Phase 6/8 mesh routing.
- **Architecture chosen:** Guest-level tailscale VM (keep daemon isolation); exit-node advertising + NAT masquerade to expose tailnet to host for `/health` check
- **Config changes (in ~/.nix-config/nixos/vms.nix, validated 2026-07-16):**
  - Added `services.tailscale.authKeyFile = "/var/lib/tailscale/authkey"` (auto-join on boot)
  - Added `services.tailscale.extraUpFlags = ["--advertise-exit-node"]` (exit-node mode)
  - Added `networking.nat` masquerade config (externalInterface=tailscale0, internalIPs masquerade)
  - Build validates clean; formatting passes
- **Pending steps:** (1) User mints auth key at login.tailscale.com, (2) Key placed in /persist/var/lib/tailscale-vm/authkey (600), (3) `make switch` + `sudo systemctl start microvm@tailscale.service`, (4) Verify VM joins via journal + admin console, (5) Laptop adds host route `100.64.0.0/10 via 192.168.101.2`, (6) Laptop runs `curl <phone_ts_ip>:8462/health` (expect 200) → sign-off flips to closed
- **Tape VM network config (existing):** Host tap vm-tailscale (192.168.101.1/24) ↔ Guest (192.168.101.2/24); virtiofs-shared /var/lib/tailscale → guest /var/lib/tailscale

## Phase 1 Runtime (stable)
- **Delivery commit:** da8849e (NPU inference: whisper, OCR, embed, classify; CPU baseline per D5; serialized priority queue with interactive preemption D8; persistent loopback backends :8464/:8465)
- **Memory file:** 20260716-phase1-built.md (phone's phase-1 build documentation)
- **Runtime:** `~/phone-agent-runtime` .deb-extraction (llama-server, whisper cmake-built, numpy/PIL/onnxruntime via .debs; requires `LD_LIBRARY_PATH=$HOME/phone-agent-runtime/lib` + `termux-wake-lock` to launch). Native Termux venv exists; legitimization (pkg install deps natively, retire hand-extracted .debs) deferred post-gate
- **Proot impedance analysis (unchanged):** Android→Termux→proot pipeline friction concentrated in proot layer; detailed in archived state
- **Stability improvement paths identified (deferred post-Phase 1 gate):** (1) Structural — remove proot, native Termux pkg install; (2) Reproducibility — codify environment knobs into versioned bootstrap.sh + launcher; (3) Testability — convert acceptance battery into repeatable verify skill
