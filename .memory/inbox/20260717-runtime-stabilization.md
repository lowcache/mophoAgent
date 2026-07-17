# Runtime stabilization P0–P4 (2026-07-17)

- P0–P3 committed 72b04a1, relay 8a879a9; laptop plan relay 20260716-0917.
- state: phase-1 sign-off CLOSED (6a11801). Operator-gate BLOCKED todo item is
  stale — replace with: "[BLOCKED] operator runs phone-agent/scripts/bootstrap.sh
  once in NATIVE Termux (stop hand-launched :8462 server first); then laptop
  runs scripts/verify.sh http://100.101.229.9:8462 (needs bearer token on
  volnix). Green battery closes stabilization and unblocks Phase 2."
- decisions candidate: runtime boundary rule (P2) is binding — proot = dev
  only; runit service owns server lifecycle; dev verifies via loopback HTTP.
- fact: whisper-cpp not in termux-main (2026-07-16); onnxruntime IS packaged.
- landmine: bootstrap sv-up while an unsupervised process holds :8462 →
  crash-loop + false-pass health wait; guarded in bootstrap.sh.
