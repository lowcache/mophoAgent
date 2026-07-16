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
- **Latest commits:** `phone` @ bdad36d (relay: native venv details), `laptop` @ f19bc77 (local hold: doc fix), `main` @ fdbe9a7

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

## Phase 1 In Progress (started 2026-07-15 ~20:00)
- **Status:** Models downloading; transcribe performance tuning underway (step 1 of 6 in build plan)
- **Environment:** Native Termux python 3.14, venv built with `UV_LINK_MODE=copy` (hardlink poisons dlopen under proot)
- **Build pivot:** Switched from uv-venv to `~/phone-agent-runtime` .deb-extraction runtime (llama-server extracted from Termux .debs, whisper cmake-built, numpy/PIL/onnxruntime via .deb payloads; `$PREFIX` untouched due to permission classifier blocking)
- **Live server state:** Rebuilt on native venv and restarted, but predates LD_LIBRARY_PATH fix; requires operator relaunch with `LD_LIBRARY_PATH=$HOME/phone-agent-runtime/lib` + `termux-wake-lock` for models to load correctly
- **Loopback test server:** Failed during perf tuning (memory pressure: ~2.5 GB free, 92s transcribe for 11s audio indicates RAM/swap constraint; llama.cpp model loading + whisper + system overhead competing)
- **Blocking item:** Native Termux launch gate. Venv + bearer fix verified in isolation; full native-session validation with termux-api access awaiting operator completion. Phone cannot proceed past step 1 without confirmation this works.
- **Timestamp format:** RFC3339 ms-truncated (correct: `2026-07-15T16:34:38.721Z`)
