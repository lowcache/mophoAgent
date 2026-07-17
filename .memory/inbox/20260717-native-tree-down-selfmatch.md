---
type: inbox
date: 2026-07-17
author: claude-phone
topic: native service tree down; process-scan self-match strike three
---

# Native runit tree died during idle gap + scan self-match repeat

- Found ~16:34 UTC: uvicorn :8462, llama :8463/:8464, whisper :8465, sshd
  :8022, runsv/runsvdir ALL gone; `sv status phone-agent` → "runsv not
  running"; supervise/pid stale since 04:14 UTC (last request logged 04:33).
  Whole native supervision tree died during a ~12 h idle gap (phantom
  process killer or app kill — proot session survived so not a full
  reboot; note PRoot FAKES /proc/uptime, don't trust it for boot time).
- Recovery is OPERATOR-ONLY per the P2 binding boundary (never launch
  servers from proot): open a native Termux session (runsvdir autostarts
  via termux-services profile.d) or run scripts/bootstrap.sh, then
  `sv up phone-agent`. Native clone already at b702c28 so restart picks
  up the stdlib-wave fix with no further deploy step.
- MISTAKE (append to mistakes.md): third strike on process-scan
  self-matching. A `/proc/*/cmdline` case-glob scan for
  `*phone-agent*main.py*` matched MY OWN shell (the pattern text is in
  the scanning command's cmdline) and `head -1` handed it to
  `kill -TERM` — killed my own shell, misread survivors as "respawned"
  server pids. Same class as the banned `pkill -f`. Rule: any
  self-written process scan must exclude `$$`/ancestors OR match on
  `/proc/*/comm` + exact cwd/exe, never on a substring that appears in
  the scan command itself.
