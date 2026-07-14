---
type: state
project: mophoAgent
last_updated: 2026-07-14
status: active
---

# System State

## Repository Structure
- **Branches:** `main` (integration base), `phone` (phases 0–7), `laptop` (phase 8)
- **Branch ownership:** claude-phone commits only to `phone`; claude-laptop owns `laptop` and performs integration merges; all branches pushed to origin (github.com/lowcache/mophoAgent)
- **Initial commit:** 79c9132 (repo scaffold: relay/, memd/, .gitignore)
- **Latest commit:** 35e238c (relay branch model documentation)

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

## Edit Verification Status
- Tether/Gemini task completed: all 15 design and phase-{2..8} files corrected per D1–D5 edits
- Stragglers verified and hand-corrected by laptop agent:
  - `design/phone-mcp-tool-schema.md`: com.chrome → com.android.chrome
  - `phone/prompts/phase-1-npu-inference.md`: removed intent-classifier-v1.gguf (not in NPU DAG)
  - `phone/prompts/phase-4-sensor-tools.md`: light-sensor error codes (SENSOR_NOT_AVAILABLE moved below SENSOR_DIRTY), GPS `-p once` removed (use cached), modem/wifi calls corrected
  - All prompts: ~/.config/phone-agent → ~/phone-agent (correct Termux root)
  - `phone/prompts/phase-7-scheduler.md`: flake_check task clarified (curl Ollama, no SSH)
- All files ready for phone clone and claude-code consumption
