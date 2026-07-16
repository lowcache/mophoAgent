# 2026-07-16 — Phase 1 built, tested, committed (claude-phone)

Commit da8849e + tag `phone-mcp-phase-1` on `phone`. Full battery green on
loopback:18462; all phase-1 acceptance criteria met (embed 32ms warm, llm
TTFT 430ms warm, transcribe 7.9s/11s clip, classify 0.98 conf, OCR exact).
Sign-off requested via relay/to-laptop/20260716-0030-phase1-built.md — that
note carries the full deviation list (whisper q8_0 not q4_0; OCR rec+numpy
projection, no det model; AUDIO_MAX_SEC=600; shared :8463 llama-server) and
platform landmines for mistakes.md/decisions.md curation:

- big.LITTLE: pin ALL backend threads to 4 (‑t6/‑t8 regress 7–11x)
- llama-server readiness = /health 200, never port-open (binds pre-load)
- Termux cmake under proot requires `PREFIX` env exported
- tar hardlinks fail under proot → python tarfile fallback for .deb unpack
- runtime binaries live in ~/phone-agent-runtime (dpkg-unaware; operator
  can legitimize with pkg install and retire it); server launch needs
  LD_LIBRARY_PATH=$HOME/phone-agent-runtime/lib
