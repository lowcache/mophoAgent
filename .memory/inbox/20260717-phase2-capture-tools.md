---
type: inbox
date: 2026-07-17
author: claude-phone
topic: phase 2 capture tools delivered
---

# Phase 2 delivered @ bf0f01f (tag phone-mcp-phase-2)

- Four capture tools (`phone.capture.{audio,image,screenshot,share}`),
  `ingest/` layer, `vad/gate.py` (Silero v5 via raw onnxruntime,
  ocr_engine-style lazy singleton), share hooks auto-installed to `~/bin`
  at startup (marker-guarded, never clobbers user scripts).
- Deploy path used: proot repo commit → native clone
  `git fetch /root/mophoAgent phone && merge --ff-only` → TERM the server
  pid → runit respawns on new code. Worked cleanly; native clone
  core.createObject=rename intact.
- Verified live: battery 5/5 (tools/list now exactly 11 — verify.sh want
  list updated), share end-to-end, VAD against real model in proot
  (pip onnxruntime works in glibc userland; model confirmed v5:
  input/state[2,b,128]/sr → output/stateN).
- Operator gate pending: pkg ffmpeg+libsndfile, uv pip soundfile,
  Termux:API mic+camera Android permissions, Shizuku/rish; then
  speech/VAD-trim, camera, screenshot, DISPLAY_OFF, Chrome-share
  acceptance + verify.sh rerun.
- termux-microphone-record cannot emit WAV (MediaRecorder); capture.audio
  records m4a then ffmpeg-transcodes — spec's "clean WAV" criterion is met
  post-transcode.
- Silero model upstream moved: files/silero_vad.onnx → 404;
  src/silero_vad/data/silero_vad.onnx is current (sha256 1a153a22…, 2.3 MB).
- Decision candidate: tether (agy) autonomous runs blocked — `agy --print`
  without `--dangerously-skip-permissions` can't execute tools, and the
  Claude Code auto-mode classifier denies launching it with that flag.
  Options: settings allowlist rule for agy, or accept inline fallback.
