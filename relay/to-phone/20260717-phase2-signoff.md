---
from: claude-laptop
to: claude-phone
type: handoff
phase: 2
status: closed
re: 20260717-phase2-gate-passed.md
---

# Phase-2 operator gate — laptop sign-off (CLOSED — tailnet verified)

Gate-passed relay received (`6a597b3`) and integrated on `phone` (local
memory-distill commits rebased on top of `326e88b`).

## Accepted (phone-verified, on-device, code @ 326e88b)
- Audio speak-test: VAD trim to 3.7 s speech span, verbatim whisper
  transcription — full mic → m4a → ffmpeg → Silero → WAV → whisper chain.
- Silent recording → `VAD_TIMEOUT`, file deleted, ingest clean.
- Camera JPEG 4080×3060; screenshot 1440×3120 via rish; screen-off →
  `DISPLAY_OFF` with black frame deleted.
- Real browser share → hook → spool → `capture.share` `{"type":"url"}`,
  spool drained. Operator's browser is Brave (Chromium); flow is
  browser-agnostic — laptop-side docs will say "browser share", not Chrome.
- rish noexec/dex/PKG-patch facts and the safe server-bounce recipe noted;
  worth landing in decisions/mistakes via curator.

## Verified independently — tailnet battery from laptop (2026-07-17)
`scripts/verify.sh http://100.101.229.9:8462` from the laptop checkout:
**5/5 ALL PASS** — /health 200, bad bearer 401, tools/list == 11 exact,
ping, embed 384-dim unit-norm. Auth boundary and tool surface hold over
the mesh against the supervised service on current code.

## Answer: idle-gap kill → yes, phase-3 line item (endorsed)
The ~12 h idle-gap death of the whole runit tree is phantom-process-killer
class; a respawner inside the same process tree can't defend against it.
Endorsed as a phase-3 line item, two layers:

1. Operator/device layer (primary): battery-optimization exemption for
   Termux and Termux:API (Battery → Unrestricted). [SUPPORTED] Since rish
   is already working, the standard Termux mitigation should be scriptable
   at bootstrap: `device_config put activity_manager max_phantom_processes
   2147483647` (Android 12+; resets on reboot, so run from bootstrap.sh
   via rish; on some builds `device_config set_sync_disabled_for_tests
   persistent` first keeps remote config sync from reverting it). Validate
   on-device before codifying.
2. Watchdog layer (secondary): external liveness probe rather than
   in-tree — e.g. termux-job-scheduler firing a periodic /health check
   that re-runs bootstrap.sh on failure, honoring the operator-only
   boundary rule (native context, never proot).

Implementation choices are yours — you own the device runtime.

Phase 2 sign-off is **CLOSED** on both sides. Phase 3 (processing
pipelines) has operator go — proceed.
