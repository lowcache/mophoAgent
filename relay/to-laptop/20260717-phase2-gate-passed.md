---
type: fyi
from: claude-phone
date: 2026-07-17
subject: Phase 2 operator gate PASSED — all acceptance green
status: open
---

# Phase 2 gate: PASSED (2026-07-17, live device)

All acceptance criteria met against the supervised service on
`http://100.101.229.9:8462`, code at `326e88b` (includes b702c28
stdlib-wave fix and the $HOME/bin service-PATH fix):

- **audio speak-test**: recording VAD-trimmed to the 3.7 s speech span
  (peak −19.8 dB); `phone.npu.transcribe` returned the spoken sentence
  verbatim (whisper-small.en-q8_0, 2.5 s). Full mic → m4a → ffmpeg →
  Silero-trim → WAV → whisper chain proven on-device.
- **audio silent**: `VAD_TIMEOUT`, recording deleted, ingest/audio clean.
- **image**: real 4080×3060 JPEG (203 KB) in ingest/images (camera grant OK).
- **screenshot**: 1440×3120 PNG via Shizuku/rish.
- **screen-off screenshot**: `DISPLAY_OFF`, all-black frame deleted.
- **real share** (browser → Termux share sheet): termux-url-opener hook
  fired, spooled valid JSON, `capture.share` → `{"type":"url",...}`,
  spool drained. (Operator uses Brave; flow is browser-agnostic.)
- **battery**: 5/5 ALL PASS @ exactly 11 tools, post-restart, new code.

Operator-side facts worth keeping:

- rish must be COPIED from /sdcard/.termux (noexec mount — PATH-adding it
  can never work) into native ~/bin; chmod 755 rish, chmod 400 the dex
  (Android 14+ app_process rejects writable dex), and patch
  RISH_APPLICATION_ID "PKG" → "com.termux". run.sh now prepends $HOME/bin
  to the service PATH (326e88b).
- The native runit tree died during a ~12 h idle gap (phantom-process-kill
  class, not a reboot); operator bootstrap brought it back. Watchdog /
  battery-optimization exemption may deserve a phase-3 line item.
- Safe server-bounce recipe from proot: match /proc/*/exe ==
  $PREFIX/bin/python* AND cwd suffix phone-agent — never cmdline
  substrings (venv python's exe resolves to the base interpreter, and
  cmdline greps self-match the scanning shell).

Phase 2 is CLOSED from the phone side. Next: Phase 3
(prompts/phase-3-processing-pipelines.md) on go-ahead.
