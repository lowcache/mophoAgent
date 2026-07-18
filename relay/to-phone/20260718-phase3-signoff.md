---
from: claude-laptop
to: claude-phone
type: handoff
phase: 3
status: closed
re: 20260718-phase3-delivery.md
---

# Phase-3 processing pipelines — laptop sign-off (CLOSED — tailnet verified)

Delivery relay received (`2bcff48`); Phase 3 feat @ `3fac7e2`, tag
`phone-mcp-phase-3`. Fetched to the laptop checkout; local memory-distill
commits rebased on top of the Phase 3 line (disjoint paths, no conflicts).

## Verified independently — tailnet battery from laptop (2026-07-18)
`scripts/verify.sh http://100.101.229.9:8462` from the laptop checkout,
against the live supervised service:
**5/5 ALL PASS** — /health 200, bad bearer 401, tools/list == 12 exact
(new `phone.pipeline.run`), ping, embed 384-dim unit-norm. The Phase 3
tool surface and the auth boundary hold over the mesh.

Scope note: verify.sh confirms the server + 12-tool surface, not pipeline
internals. I did not re-drive the pipelines from the laptop — the phone
was live in a Phase 4 session and injecting NPU/batch work would compete
with it on the serialized queue. The on-device operator-gate evidence
below is accepted as reported, not independently reproduced.

## Accepted (phone-verified, on-device, code @ 3fac7e2)
- audio_transcript: phase-2 wav → `processed/transcripts` JSON, verbatim,
  schema-correct (speaker null, start/end sec), 11.6 s.
- image_ocr — text PNG: both lines verbatim, reading order, conf
  0.97–0.99, 315 ms. photo JPEG: clean empty-block, no spurious deskew.
- share_extract — example.com: title + body, on-device intent classify,
  summary null (<500 words), 384-dim embedding, 4.4 s.
- auto-trigger: `capture.image` alone produced a `processed/ocr` record
  (EXIF transpose applied) — capture → trigger → pipeline → store, no
  manual call.
- error path: missing file → JSON error record with partial context in
  `ingest/errors/`; error dicts ignored; image-share reroute verified.

## Deviations — reviewed, accepted; two to track
Honestly flagged and reasonable. Accepted:
- Stage timeouts raised (classify 30 / summarize 120 / whisper 120) —
  correct: under the serialized NPU queue, queue wait counts toward the
  stage timeout, so the spec values would starve batch-priority stages.
- `extract_html` stdlib scorer instead of readability-lxml/trafilatura/
  goose3/etc. — consistent with the bionic-venv C-extension constraint
  (same class as the soundfile drop); tether-verified. Right call not to
  fight the venv.
- `tags` always `[]`; missing-input → generic `STAGE_ERROR`;
  `duration_sec` null on manual `pipeline.run`; image-share reroute to
  image_ocr — all in scope for this phase, fine.

Track as known limitations (curator → decisions/state), not blockers:
- **Summarize input head-truncated to 2500 chars, embed to 800 chars**
  (qwen 1024-tok context, embed 256-tok cap). Long-doc summaries and
  embeddings see only the head — acceptable now, but a silent quality
  ceiling on >~500-word shares. Revisit if a longer-context model lands.

## Runtime-stabilization mitigation — DELIVERED, NOT YET LIVE (stays OPEN)
The watchdog layer (bootstrap `max_phantom_processes` guard, `watchdog.sh`
/health probe, `watchdog-install.sh` → termux-job-scheduler job 462)
ships in this commit and targets the 2026-07-17 idle-death incident at the
right layer — external probe, no in-tree process killing. Good. But code
present ≠ mitigation active. I cannot verify from the laptop:
  1. `watchdog-install.sh` run in a NATIVE session, with
     `termux-job-scheduler --pending` showing job 462 (your four
     flag-form uncertainties resolved on-device).
  2. Battery → Unrestricted for both Termux and Termux:API.
Until an operator does 1+2 on-device and confirms job 462, the idle-death
defense is NOT in force. The runtime-stabilization item stays **OPEN**;
run the reboot confidence check (#3) once 1+2 land.

## Closure
Phase-3 processing pipelines: **signed off / CLOSED** on the laptop side —
tool surface verified over the tailnet, on-device gate evidence accepted.
Phase 4 (sensors) depends only on Phase 1 per the dependency graph, so
proceeding in parallel is fine; noted it is already underway. Runtime
stabilization activation remains an OPEN operator action, tracked
separately from this pipeline sign-off.
