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
- **Latest commits:** `phone` @ 5a13bb3 (phase-1 gate runbook relay); `laptop` @ ce3e8d5; `main` @ fdbe9a7
- **WIP branches:** claude-phone on feature branch `npu-inference-layer-phase1` (reconciliation with `phone` pending once gate passes)
- **Integration status:** Phase 1 delivered (da8849e) + relay handoff (b83ca19). Phase-1 gate runbook pushed (5a13bb3). Operator gate active on Galaxy S26 (native Termux launch + acceptance battery) — awaiting results before Phase 2.

## phoneAgentBuild Organization
- `design/` — architecture specifications: phone-mcp-tool-schema.md, npu-pipeline-graph.md, trigger-propagation-model.md, offline-autonomy-model.md, deepseek-system-prompt.md
- `phone/` — phases 0–7: PHONE-ENV.md (build context), `prompts/phase-{0..7}-*.md`
- `laptop/` — phase 8 prompt and integration work
- `DECISIONS.md` — authoritative D1–D10 (overrides contradictions in design/ and prompts/)
- `build-plan.md` — eight-phase structure with commit templates

## Relay Dropbox (relay/)
- `relay/to-laptop/` — messages from claude-phone to claude-laptop
- `relay/to-phone/` — messages from claude-laptop to claude-phone
- `relay/archive/` — closed message threads (phase-0-signoff moved here 2026-07-15)
- Message protocol: markdown files on author's branch; frontmatter `type: blocker|question|decision-request|handoff|fyi`

## Phase 0 Verification and Sign-Off (2026-07-15)
- **Delivery commit:** 3b9155c (claude-phone, bind deviation self-resolved)
- **Verification method:** Laptop extracted phone-agent/ into isolated Python 3.13 venv (mcp 1.28.1), ran full acceptance battery against live server
- **Result:** ✓ APPROVED. All acceptance criteria pass: `/health` 200 (no auth), `tools/list` returns both tools with descriptions, JSON shapes correct, malformed JSON → 400 (no crash), refuse start without token → exit 1 with hint
- **Polish fixes applied (commit 24c6886, reapplied 6ef93cc):**
  - Tool docstrings: `phone.system.ping` and `phone.system.state` now carry descriptions (surface in tools/list for on-device LLM tool selection)
  - Bearer token comparison hardened: bytes compare with `hmac.compare_digest` (constant-time; closes timing side-channel on non-ASCII headers)
  - Both changes re-verified end-to-end before commit
- **D1 bind deviation (resolved, no amendment):** TS IP bind falls back to 0.0.0.0 (DNS-rebind protection under Tailscale VPN works), SDK Host-header check disabled, Accept header required. All per D1 constraints.

## Phase 1 Complete & Operator Gate Live (2026-07-16)
- **Delivery commit:** da8849e (NPU inference: whisper, OCR, embed, classify; CPU baseline per D5; serialized priority queue with interactive preemption D8; persistent loopback backends :8464/:8465)
- **Memory file:** 20260716-phase1-built.md (phone's phase-1 build documentation)
- **Relay handoff:** b83ca19 (battery results, deviations, operator TODOs)
- **Gate runbook:** relay/to-phone/20260716-0355-phase1-operator-gate.md pushed @ 5a13bb3. Runbook covers: path conflict Q1 (~/phone-agent vs ~/mophoAgent/phone-agent), branch reconciliation Q2 (npu-inference-layer-phase1 → phone), native launch + acceptance battery (health 200, auth 401, tools/list, termux-battery-status, Tailscale reachability), proot-independence verification.
- **Gate status:** Active on Galaxy S26 (since 2026-07-16). Claude-phone running native Termux launch + acceptance tests. Awaiting results via relay/to-laptop/.
- **Runtime:** `~/phone-agent-runtime` .deb-extraction (llama-server, whisper cmake-built, numpy/PIL/onnxruntime via .debs; requires `LD_LIBRARY_PATH=$HOME/phone-agent-runtime/lib` + `termux-wake-lock` to launch). Native Termux venv already exists; full legitimization (pkg install deps natively, retire hand-extracted .debs) pending after gate passes.
- **Proot impedance analysis:** Android→Termux→proot pipeline friction concentrated in proot layer. Failure classes: linker namespace rejects hardlinks; tarfile extract fails (link2symlink fallback); getprop unavailable under proot; Android sysroot inaccessible (PREFIX export required); pkg refuses uid 0 (hand-extraction to ~/phone-agent-runtime, dpkg-blind); termux-api unreachable from proot (forces native-only server); proot session-dependent server dies with proot exit. Bionic limits (orthogonal): abi3 wheels need `patchelf --add-needed libpython3.14.so` (cryptography's _rust.abi3.so); no opencv/pyclipper wheels (numpy segmentation fallback). SoC/device (orthogonal): big.LITTLE thread pinning (‑t4 vs ‑t8 = 7–11× regression); ~2.5 GB free RAM/swap pressure.
- **Stability improvement paths identified:** (1) Structural — remove proot from runtime (native Termux `pkg install` for deps); research whether Claude Code + full build runs in native Termux (bionic) without proot userland. (2) Reproducibility — codify environment knobs (UV_LINK_MODE=copy, ANDROID_API_LEVEL=24, PREFIX export, patchelf --add-needed, thread pins ‑t4 ‑tb4, LD_LIBRARY_PATH, termux-wake-lock) into versioned bootstrap.sh + launcher with fast-fail on proot detection. (3) Testability — convert phase-1 acceptance battery into repeatable verify skill.
- **Timestamp format:** RFC3339 ms-truncated (correct: `2026-07-15T16:34:38.721Z`)
