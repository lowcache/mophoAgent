---
type: state
project: mophoAgent
last_updated: 2026-07-15
status: active
---

# System State

## Repository Structure
- **Branches:** `main` (integration base), `phone` (phases 0–7), `laptop` (phase 8)
- **Branch ownership:** claude-phone owns `phone` branch (phases 0–7); claude-laptop owns `laptop` branch (phase 8) and performs integration merges. Main is integration-only. Exception: 2026-07-15, laptop applied polish fixes to phone branch at operator direction (flagged in relay/to-phone/20260715-1139-phase0-signoff.md).
- **Initial commit:** 79c9132 (repo scaffold: relay/, memd/, .gitignore)
- **Latest commits:** `phone` @ 24c6886 (polish fixes), `laptop` @ 35e238c, `main` @ fdbe9a7

## phoneAgentBuild Organization
- `design/` — architecture specifications: phone-mcp-tool-schema.md, npu-pipeline-graph.md, trigger-propagation-model.md, offline-autonomy-model.md, deepseek-system-prompt.md
- `phone/` — phases 0–7: PHONE-ENV.md (build context for claude-code in proot), `prompts/phase-{0..7}-*.md` (8 phase prompts for sequential build)
- `laptop/` — phase 8 prompt and integration work
- `DECISIONS.md` — authoritative D1–D10 (overrides all contradictions in design/ and prompts/)
- `build-plan.md` — eight-phase structure with commit message templates

## Relay Dropbox (relay/)
- `relay/to-laptop/` — messages from claude-phone to claude-laptop
- `relay/to-phone/` — messages from claude-laptop to claude-phone
- `relay/archive/` — closed message threads
- Message protocol: markdown files with frontmatter `type: blocker|question|decision-request|handoff|fyi`. Replies appended to same file. Messages ride on author's own branch (no cross-branch edits). Relay complements git; relay-worthy persistence forwarded to memd inbox by curator.

## Phase 0 Verification and Sign-Off (2026-07-15)
- **Delivery commit:** 3b9155c (claude-phone, bind deviation self-resolved)
- **Verification method:** Laptop extracted phone-agent/ into isolated Python 3.13 venv (mcp 1.28.1), ran full acceptance battery against live server (bind fell back to 127.0.0.1 with no TS IP configured)
- **Result:** ✓ APPROVED. All acceptance criteria pass: `/health` 200 (no auth), `tools/list` returns both tools with descriptions, JSON shapes correct, missing/wrong bearer → 401, malformed JSON → 400 (no crash), refuse start without token → exit 1 with hint
- **Polish fixes applied (commit 24c6886, operator-directed on phone branch):**
  - Tool docstrings: `phone.system.ping` and `phone.system.state` now carry descriptions (surface in tools/list for on-device LLM tool selection)
  - Bearer token comparison hardened: `main.py` uses `hmac.compare_digest` instead of `!=` (constant-time; closes timing side-channel)
  - Both changes re-verified end-to-end before commit
  - Ownership deviation flagged in relay so phone agent is aware
- **Open item (non-blocking Phase 0, Phase 1 entry gate):** Native Termux run unverified. Phase 0 smoke tests ran under proot-distro (no termux-api needed). D2 requires native runtime; must confirm `pkg install python uv` + `uv pip install` can resolve pydantic-core (Rust wheel) on bionic before Phase 1 starts. Proot verification is functionally sufficient for Phase 0 as shipped.
- **Timestamp format:** RFC3339 ms-truncated (correct: `2026-07-15T16:34:38.721Z`)
- **D1 bind deviation (resolved, no amendment):** TS IP bind falls back to 0.0.0.0 (DNS-rebind protection works under Tailscale VPN), SDK Host-header check disabled, Accept header required in JSONRPC call. All sound per D1 constraints.
