# Phase-3 laptop sign-off — curator notes (2026-07-18)

Phase 3 (processing pipelines) signed off laptop-side. Relay:
`relay/to-phone/20260718-phase3-signoff.md`. Code @ `3fac7e2`, tag
`phone-mcp-phase-3`. Laptop `scripts/verify.sh` over tailnet
(100.101.229.9:8462) = **5/5 @ 12 tools** (new `phone.pipeline.run`).

## For state.md
- Phase 3 status → CLOSED (pipelines): audio_transcript, image_ocr,
  share_extract, capture auto-trigger, manual `phone.pipeline.run`.
  Tool count 11 → 12. verify.sh updated to assert 12 (resolves the
  Phase-2/Phase-3 tool-count discrepancy todo).
- Branch note: local `phone` had 4 memory-distill commits that had
  diverged from `origin/phone`; rebased onto the Phase 3 line (2bcff48),
  disjoint paths. Sign-off committed locally, **push held** (phone live
  in Phase 4 session — avoid non-ff race on the shared branch).

## For decisions.md (known limitations, not blockers)
- Share pipeline: summarize input head-truncated to 2500 chars, embed to
  800 chars (qwen 1024-tok ctx, embed 256-tok cap). Long-doc summaries/
  embeddings see only the head — silent quality ceiling on >~500-word
  shares. Revisit with a longer-context model.
- URL extraction uses a stdlib `html.parser` scorer (`extract_html.py`);
  every readability lib (readability-lxml, trafilatura, justext, goose3,
  newspaper4k, resiliparse) needs lxml/C ext that won't load in the
  bionic venv — same class as the soundfile drop. Tether-verified.

## For todo.md — runtime-stabilization item STAYS OPEN
Watchdog code delivered (bootstrap `max_phantom_processes` guard,
`watchdog.sh` /health probe, `watchdog-install.sh` → termux-job-scheduler
job 462) — but NOT yet activated on-device. Still requires operator:
  1. Run `watchdog-install.sh` in a NATIVE session; confirm job 462 via
     `termux-job-scheduler --pending` (4 flag-form uncertainties to
     resolve on-device).
  2. Battery → Unrestricted for Termux + Termux:API.
  3. Optional reboot confidence check after 1+2.
Code present ≠ idle-death defense in force. Do not close the CRITICAL
stabilization todo until 1+2 confirmed.
