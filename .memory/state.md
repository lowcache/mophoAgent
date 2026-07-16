---
type: state
project: mophoAgent
last_updated: 2026-07-15
status: active
---

# System State

## Repository Structure
- **Branches:** `main` (integration base), `phone` (phases 0–7), `laptop` (phase 8)
- **Branch ownership:** claude-phone owns `phone` branch (phases 0–7); claude-laptop owns `laptop` branch (phase 8) and performs integration merges. Main is integration-only.
- **Latest commits:** `phone` @ b83ca19 (relay: phase-1 handoff); `laptop` @ ce3e8d5 (3 ahead, pending rebase → push); `main` @ fdbe9a7
- **Integration status:** Phone pushed phase-1 code + relay (2026-07-16). Laptop rebase queued (no conflicts predicted).

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

## Phase 1 Complete (committed 2026-07-16)
- **Delivery commit:** da8849e (NPU inference: whisper, OCR, embed, classify; CPU baseline per D5; serialized priority queue with interactive preemption D8; persistent loopback backends :8464/:8465)
- **Memory file:** 20260716-phase1-built.md (phone's phase-1 build documentation)
- **Relay handoff:** b83ca19 (battery results, deviations, operator TODOs)
- **Runtime:** `~/phone-agent-runtime` .deb-extraction (llama-server, whisper cmake-built, numpy/PIL/onnxruntime via .debs; requires `LD_LIBRARY_PATH=$HOME/phone-agent-runtime/lib` + `termux-wake-lock` to launch)
- **Testing:** Loopback server failed during perf tuning (RAM/swap constraint with ~2.5 GB free; qwen model resident; whisper bench isolation needed to characterize)
- **Operator gate:** Native Termux launch validation with LD_LIBRARY_PATH fix and termux-api access required before Phase 2.
- **Timestamp format:** RFC3339 ms-truncated (correct: `2026-07-15T16:34:38.721Z`)
