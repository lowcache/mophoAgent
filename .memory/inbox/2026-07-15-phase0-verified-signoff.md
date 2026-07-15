# Phase 0 verified and signed off (2026-07-15)

Laptop-side verification of the phone's Phase 0 delivery (`phone` branch,
was @ 3b9155c). Extracted `phone-agent/` into an isolated laptop venv
(Python 3.13 + mcp 1.28.1) and ran the full acceptance battery against a
live server (bind fell back to 127.0.0.1, no TS IP set).

## Verdict: APPROVED
All acceptance criteria pass: `/health` 200; `tools/list` both tools;
`ping`/`state` JSON matches spec; missing/wrong token → 401; malformed JSON
→ 400 (no crash); missing token file → exit 1. Automate crash-restart is
device-side, accepted as documented. Phone's bind-deviation thread
(0.0.0.0 fallback, DNS-rebind disable, Accept header) is sound and
self-resolved — no D1 amendment.

## Two polish fixes applied by laptop ON the phone branch (operator-directed)
- Added docstrings to `phone.system.ping` / `phone.system.state` — they were
  empty in `tools/list`; the on-device agent selects tools by description.
- Constant-time bearer compare: `hmac.compare_digest` replaces `!=` in
  `main.py` (closes a token-timing side-channel).
Both re-verified end-to-end before commit. Commit message:
`polish(phone-mcp): tool docstrings + constant-time bearer compare`.

## Ownership deviation to record
lowcache directed the laptop agent to commit these fixes directly to the
`phone` branch. Per DECISIONS.md the phone owns that branch and laptop is
integration-only; this was an explicit operator override, not a convention
change. Flagged to phone in `relay/to-phone/20260715-1139-phase0-signoff.md`.

## Open item (non-blocking for Phase 0, gates Phase 1)
Native Termux run still unverified — phone's smoke tests ran under proot.
Phase 0 uses no termux-api so proot is functionally sufficient, but D2
requires native runtime and `pydantic-core` is a Rust wheel that may not
build on bionic. Confirm native `pkg install python uv` + `uv pip install`
before Phase 1. Add to todo as a Phase-1 entry gate.
