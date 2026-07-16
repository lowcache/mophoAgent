---
from: claude-phone
type: report
phase: 1
status: open
re: 20260716-0355-phase1-operator-gate.md
---

# Phase-1 operator gate — results (PASS) + Q1/Q2 answers

## Q1 — path: not a conflict
`~/phone-agent` is a **symlink** → `~/mophoAgent/phone-agent` (created Jul 14,
satisfies D2). Both earlier notes describe the same directory. Launch line
`cd ~/phone-agent` is correct as written.

## Q2 — branch: no such branch exists
`npu-inference-layer-phase1` is not a git branch in either clone — it was the
Claude Code session title in the statusline. Native + proot clones are both on
`phone` (HEAD 5a13bb3 before this note); da8849e and tag `phone-mcp-phase-1`
are contained. Nothing to merge.

## Gate results (native launch, verified from proot over loopback)

Operator launched in a native Termux session with termux-wake-lock held.
First attempt failed on a missing space (`...runtime/lib/.venv/bin/python`
parsed as one env assignment → `main.py: command not found`); corrected line
started cleanly.

- server pid 8467, env `LD_LIBRARY_PATH=$HOME/phone-agent-runtime/lib`,
  cwd `~/phone-agent`
- ancestry: python(8467) ← native bash(31703) ← Termux app (TERMUX_APP_PID
  31659; hidden from /proc by Android hidepid — expected). **No proot in the
  chain**, so proot-session exit cannot take it down.
- GET /health → **200**; bad bearer on /mcp → **401**
- tools/list → **7 tools** (npu.classify/embed/llm_infer/ocr/transcribe,
  system.ping/state). Server runs stateless streamable-HTTP (JSON responses,
  no mcp-session-id) — laptop client note.
- eager backends up: embed :8464 → 200, whisper :8465 → 200
- live smoke: ping 19ms; embed "gate check" → 384-dim, norm 1.0000, 66ms
- `termux-battery-status` → valid JSON (77%, DISCHARGING, health GOOD,
  25.3°C). termux-api works natively — phase-2 prereq satisfied.

Remaining for you: tailnet `GET /health` 200 from volnix over Tailscale, and
if you want the literal survive-proot-exit curl, run it after this proot
session ends — ancestry above already guarantees the outcome.

Requesting phase-1 sign-off close.
