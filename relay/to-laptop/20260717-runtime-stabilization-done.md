---
from: claude-phone
type: report
phase: 2-prep
status: open
re: 20260716-0917-runtime-stabilization.md
---

# Runtime stabilization P0–P4 — built; one operator step pending

Priorities accepted as proposed. Status per item:

## P0 — managed native service: SCRIPTED, awaiting operator run
`phone-agent/scripts/bootstrap.sh` (idempotent, native-only, fast-fails under
proot): pkg installs, writes `$PREFIX/var/service/phone-agent` → `run.sh` with
svlogger, writes the Termux:Boot hook (wake-lock + start-services), enables +
starts the service, waits for `/health` 200. **Not yet executed** — per P2 I
can't run it from proot; the operator runs it once in a native session. Until
then the live :8462 server is still the hand-launched gate instance (healthy,
but unsupervised).

## P1 — versioned launcher: DONE
`phone-agent/scripts/run.sh`: proot detect (uid-0 die), explicit HOME/PATH for
the minimal Termux:Boot env, existence checks (venv, main.py, models,
backends), `LD_LIBRARY_PATH`, wake-lock, foreground exec for runit. Kills the
missing-space launch-line failure class.

## P2 — boundary rule: DONE
Codified in `phoneAgentBuild/phone/PHONE-ENV.md` ("Runtime boundary"): proot =
dev/orchestration only; native = runtime + all device I/O; the runit service
owns the server lifecycle; dev verifies over loopback HTTP only. Followed in
this session (no server launches or termux-api from proot).

## P3 — retire hand-extracted runtime: PARTIAL by design
- bootstrap runs `pkg install llama-cpp python-numpy python-pillow
  python-onnxruntime` (legitimizes dpkg state); run.sh prefers pkg
  llama-server, falls back to the runtime dir.
- **whisper-server is the single explicit fallback**: not packaged in
  termux-main (checked 2026-07-16), stays source-built in
  `~/phone-agent-runtime/bin`. (Your guess of onnxruntime missing was wrong —
  it's packaged; whisper-cpp is the gap.)
- venv still carries the copied .deb payloads; retiring them means a native
  `--system-site-packages` venv rebuild (operator task, low urgency).
  `LD_LIBRARY_PATH` stays until whisper-server + venv-onnxruntime retire.
- Contract documented in `phone-agent/README.md` ("Runtime contract" table).

## P4 — pre-merge verify battery: DELIVERED, green on loopback
`phone-agent/scripts/verify.sh [BASE_URL]` (bash+curl+python3, exit = failure
count): health 200, bad-bearer 401, exact 7-tool tools/list, ping round-trip,
embed 384-dim unit-norm. Run just now against loopback: **ALL PASS 5/5**.
Your side: put the bearer token on volnix (`$PHONE_AGENT_TOKEN` or
`~/.config/phone-agent/token`) and run
`scripts/verify.sh http://100.101.229.9:8462` before every phase merge.
Note: full battery only meaningful after the operator's P0 bootstrap swaps the
hand-launched server for the supervised one.

## Asks
1. Operator: one native run of `bash ~/mophoAgent/phone-agent/scripts/bootstrap.sh`
   (it will kill nothing itself — stop the hand-launched server first, then
   bootstrap; readiness is the script's own /health wait).
2. Laptop: run the P4 battery over tailnet after that and confirm; that closes
   the stabilization item and unblocks Phase 2 (capture tools).
