---
type: fyi
from: claude-phone
date: 2026-07-17
subject: Phase 2 delivered — capture tools live; operator gate pending
status: open
---

# Phase 2: Capture Tools — Delivered

Commit `bf0f01f` on `phone`, tag `phone-mcp-phase-2`. Four new MCP tools live
on the tailnet endpoint (`http://100.101.229.9:8462`): `phone.capture.audio`,
`phone.capture.image`, `phone.capture.screenshot`, `phone.capture.share`.
Plus `ingest/` (directory tree + file naming), `vad/` (Silero VAD gate, raw
onnxruntime), and share-sheet hooks auto-installed to `~/bin` at startup.

## Verified (2026-07-17, live server, post-deploy)

- verify.sh battery equivalent: 5/5 ALL PASS from proot against the tailnet
  IP (health 200, bad bearer 401, tools/list == 11 exact, ping, embed
  384-dim unit-norm). verify.sh's exact-tool-set assertion updated 7 → 11.
- `phone.capture.share` end-to-end: spooled URL entry → `{"type":"url",...}`,
  spool drained, entry archived to `shares/`; 1s timeout → clean `TIMEOUT`.
- Ingest tree (15 subdirs incl. `queue/delivering/`) created at startup;
  both hooks installed 0755 with marker.
- VAD [ESTABLISHED]: model.silero is v5 (`input`/`state[2,b,128]`/`sr` →
  `output`/`stateN`, dumped via onnxruntime); gate runs the real model —
  silence and noise clips → no spans; span merge/pad/min-speech math checked
  with injected probabilities.
- Error paths return typed dicts, server stays up: `PERMISSION_DENIED`
  (camera, mic), `SHIZUKU_NOT_RUNNING` (rish absent).

## Operator gate remaining (device actions, then acceptance re-test)

1. `pkg install ffmpeg libsndfile` (native; MediaRecorder can't emit WAV —
   capture.audio transcodes via ffmpeg; soundfile needs libsndfile)
2. `uv pip install soundfile` into `~/phone-agent/.venv` (native)
3. Android Settings → Apps → Termux:API → Permissions → grant Microphone
   and Camera
4. Shizuku running + `rish` on PATH (screenshot tool)
5. Acceptance: speak-test audio (VAD trim to speech span), silent recording
   → `VAD_TIMEOUT` + file deleted, image capture, screenshot, screen-off
   screenshot → `DISPLAY_OFF`, Chrome share → capture.share
6. Re-run `scripts/verify.sh` (expects 11 tools now)

VAD model (`vad/model.silero`, 2.3 MB, sha256 `1a153a22…`) is gitignored and
already placed on-device; note the upstream path moved to
`src/silero_vad/data/silero_vad.onnx` (old `files/` URL in the phase prompt
404s).

Note: tether autonomous runs are currently blocked in the Claude Code
session (permission classifier denies `--dangerously-skip-permissions`);
research/verification for this phase was done inline instead.
