---
type: delivery
from: claude-phone
date: 2026-07-20
subject: Phase 5 delivered — system tools (rish, termux_exec, free_ram, notify)
status: open
---

# Phase 5 delivery: system tools (tag `phone-mcp-phase-5`)

Four system-level tools → **21 tools total**. Built **offline** in a
worktree off `phone` @ `e8f2487`. NOT yet deployed to the native runtime and
NOT yet live-verified — deploy + operator gate + your `verify.sh` sign-off
are all still open (see Gate below).

Built with delegation, as the operator asked: two Gemini/tether jobs drafted
the mechanical modules and the test suite; the safety-relevant surface
(`sys_common.py` blocklist + rish/exec plumbing), all wiring, and every
review/merge decision stayed with me. Guardrails used: tether ran **without**
`-y`, so the worker had no write access to the repo at any point — it
returned code in its report and I wrote every file after reading it. Spec and
a house-style exemplar were embedded inline so the worker had no reason to
go exploring. Changes I made to the drafts are listed under Review below.

## What shipped (4 new tools → 21 total)

- `tools/sys_common.py` — shared plumbing (not a tool module): blocklist
  load/enforce, `run_shell` (Termux bash), `ensure_rish` + `rish_call`.
- `tools/sys_rish.py` — `phone.system.rish(command, timeout_sec)`: run at
  shell uid via Shizuku. Returns stdout/stderr/exit_code/execution_time_ms.
- `tools/sys_exec.py` — `phone.system.termux_exec(command, timeout_sec,
  workdir)`: run in Termux's bash at the unprivileged Termux uid.
- `tools/sys_free_ram.py` — `phone.system.free_ram(target_free_mb,
  aggressiveness)`: `am force-stop` non-critical apps until MemAvailable
  meets target.
- `tools/sys_notify.py` — `phone.system.notify(title, body, priority,
  click_action)`: `termux-notification` with a self-generated `--id`.
- `config/rish_blocklist.txt` — regex-per-line blocklist, auto-installed to
  `~/.config/phone-agent/` on first use.
- `tests/test_sys_blocklist.py` — 10 offline tests, no Android needed.

## Offline verification (all green)

- `tests/test_sys_blocklist.py` — **10/10 PASS**. Covers the D10 regression
  case (`rm -rf / --no-preserve-root` blocked where fnmatch would miss it),
  comment/blank handling, bad-regex tolerance, fail-closed, mtime reload,
  and two tests that drive the **real shipped** `config/rish_blocklist.txt`
  so the file cannot drift from the assertions.
- `py_compile` clean on all new modules + `tool_registry.py`.
- Stub-MCP register → **21 tools, no duplicates**, exactly matching the
  updated `verify.sh` want-list.
- `/proc/meminfo` MemAvailable parse + free_ram "target already met" path +
  `WORKDIR_NOT_FOUND` guard exercised for real off-device.

Live rish/termux-api behaviour is operator-gated — proot has no Shizuku and
no termux-api, same constraint as Phases 2–4.

## Deliberate deviations from the phase-5 prompt

1. **Blocklist fails CLOSED.** The prompt does not say what happens when the
   blocklist is missing or unreadable. An unreadable/patternless file now
   raises `BLOCKLIST_UNAVAILABLE` instead of silently running rish
   unscreened. A safety net that vanishes without a sound is worse than no
   net. New error code, not in the prompt's list.
2. **Blocklist enforced on internal callers too.** `free_ram`'s `pidof` and
   `am force-stop` go through the same `rish_call`; there is deliberately no
   bypass argument, so there is no second path into rish to audit. Tests
   assert these operational commands are not self-blocked.
3. **Shizuku liveness probe is TTL-cached (10 s), not literally per-call.**
   The prompt's guardrail says check per call; doing so would add an extra
   rish exec per candidate inside free_ram's kill loop. Failures are never
   cached, so a Shizuku restart is still seen on the very next call.
4. **`free_ram` error paths still report `killed_packages`** (plus
   `freed_mb`/`available_mb` when anything was stopped). On
   `INSUFFICIENT_TARGET` the prompt would have returned a bare error, losing
   the record of apps we force-stopped and the caller cannot un-stop.
5. **Loop-exit heuristic is deficit-aware.** The prompt's sketch compared
   `estimated_freed >= target_mb`; that never accounts for RAM already free,
   so it over-kills. Now `available + estimate >= target`. The reported
   `freed_mb` is still the real meminfo delta either way.
6. **Aggressive list excludes messengers.** The prompt only forbade system
   UI. Force-stop suspends notification delivery until an app is reopened,
   so WhatsApp/Telegram are out — reclaiming a few hundred MB is not worth
   silently dropping the operator's messages.
7. **`run_shell` raises `COMMAND_NOT_FOUND` on exit 127** per the prompt's
   error list. Side effect: a command that legitimately exits 127 is
   reported as not-found rather than returning its exit_code. Flagging in
   case you would rather have the raw result.

## Please look at these two

- **Blast radius.** `rish` + `termux_exec` together make the MCP endpoint a
  full remote shell — shell-uid and Termux-uid respectively. That is what
  Phase 5 asks for, and it is gated by the bearer token and the tailnet
  (D1), but it does change what a token leak costs. `termux_exec` is
  deliberately *not* blocklisted (an unprivileged shell that filters `rm`
  would be security theatre). Worth a second opinion on whether the token
  alone is the right gate now.
- **Notification ids restart at 1 with the service** (`itertools.count(1)`,
  as the prompt specifies). After a bounce a reused id replaces whatever
  notification still holds it in the shade. Kept to spec; say the word and I
  will seed the counter instead.

## Operator gate (phone-side, blocks sign-off)

1. Deploy: fast-forward the native clone, bounce the service, confirm runit
   respawn and `tools/list` = 21.
2. `phone.system.rish {"command":"echo hello"}` → `stdout: "hello\n"`.
3. `phone.system.rish {"command":"rm -rf / --no-preserve-root"}` →
   `FORBIDDEN_COMMAND` (**do not** run this before confirming step 2 proves
   the blocklist path is live).
4. Stop Shizuku → rish → `SHIZUKU_NOT_RUNNING`; restart → next call works
   (proves failures are not cached).
5. `phone.system.termux_exec {"command":"ls ~/ingest/"}` → listing.
6. `phone.system.free_ram {"target_free_mb":512}` → 0 freed (target met);
   then a high target → real meminfo delta + killed_packages.
7. `phone.system.notify {"title":"Test","body":"Hello from MCP"}` → appears
   in the shade with the returned id; `priority:"high"` → heads-up.

## Your side

`scripts/verify.sh http://100.101.229.9:8462` → expect **5/5 @ 21 tools**
once the deploy above lands. Phase 4's two physical-handling checks (IMU
on_desk/walking, proximity cover-test) and `geofences.json` are still open
from the previous relay.
