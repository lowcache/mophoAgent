#!/data/data/com.termux/files/usr/bin/bash
# One-shot installer — OPERATOR runs this ONCE natively: bash scripts/watchdog-install.sh
# Schedules watchdog.sh via termux-job-scheduler every 15 min, persisted across
# reboots. Idempotent: cancels any prior job 462 before scheduling.
set -euo pipefail

die() { echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] && die "running under proot/root — run in NATIVE Termux"
command -v termux-job-scheduler >/dev/null \
    || die "termux-job-scheduler not found — pkg install termux-api (and the Termux:API app)"

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
WATCHDOG="$SCRIPT_DIR/watchdog.sh"
JOB_ID=462

[ -f "$WATCHDOG" ] || die "watchdog.sh missing at $WATCHDOG"
chmod +x "$WATCHDOG"

echo "==> cancel prior job $JOB_ID (ignore failure if none / flag mismatch)"
termux-job-scheduler --cancel --job-id "$JOB_ID" 2>/dev/null || true

echo "==> schedule watchdog job $JOB_ID (every 15 min, persisted)"
termux-job-scheduler \
    --job-id "$JOB_ID" \
    --script "$WATCHDOG" \
    --period-ms 900000 \
    --persisted true

echo "OK: job $JOB_ID -> $WATCHDOG every 900000 ms, persisted across reboots"
echo "verify:  termux-job-scheduler -p    # pending jobs should list job $JOB_ID"
echo "log:     $HOME/.local/state/phone-agent/watchdog.log (written only on health failures)"
