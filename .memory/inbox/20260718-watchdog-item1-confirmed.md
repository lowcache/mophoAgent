# Runtime-stabilization gate — item #1 CONFIRMED (2026-07-18)

Operator ran `watchdog-install.sh` in a native session and verified the
termux-job-scheduler job is **pending**. Job ID is **462** (matches the
Phase 3 delivery + sign-off; an earlier "4623" in chat was a typo).

## Effect on the CRITICAL runtime-stabilization todo
- Item #1 (watchdog-install + job 462 pending) → **DONE**.
- Item #2 (Battery → Unrestricted for Termux + Termux:API) → **still OPEN**.
  Until #2, the job scheduler + phantom mitigation don't survive an OS
  app-kill, so the 2026-07-17 idle-death defense is not yet fully in force.
- Item #3 (optional reboot confidence check) → pending, do after #2.

Do NOT close the stabilization todo until item #2 is confirmed on-device.
