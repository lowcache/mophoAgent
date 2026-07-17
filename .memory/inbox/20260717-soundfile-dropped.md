---
type: inbox
date: 2026-07-17
author: claude-phone
topic: soundfile dependency removed from capture.audio
---

# soundfile/libsndfile dropped — stdlib wave instead

- Operator hit hardlink errors running `uv pip install soundfile` in the
  native venv (numpy dep re-resolution). Venv inspected: undamaged (numpy
  2.4.4 android_aarch64 intact, soundfile never landed).
- Deeper problem: pip/uv soundfile ships a manylinux wheel with bundled
  glibc libsndfile — would fail bionic dlopen even if it installed (same
  class as [[project-uv-dlopen-poisoned-inodes]]).
- Fix: capture.audio WAV I/O rewritten on stdlib `wave` (ffmpeg already
  guarantees 16-bit mono PCM); soundfile removed from pyproject.toml.
  Round-trip + real-model VAD pipe tested in proot.
- Operator gate correspondingly shrinks: `pkg install ffmpeg` +
  mic/camera permissions + Shizuku/rish only. No pip installs remain.
- Mistake candidate: the original phase-2 runbook prescribed
  `pkg install libsndfile` + `uv pip install soundfile` — a pip-wheel
  native-lib dependency should never have been prescribed for the bionic
  venv given the known dlopen landmine.
