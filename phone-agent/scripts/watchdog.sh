#!/data/data/com.termux/files/usr/bin/bash
# phone-agent watchdog — external liveness probe fired by termux-job-scheduler
# (runs OUTSIDE the runit tree so it survives a phantom-process tree kill).
# Healthy: /health answers 200 with body containing "ok" on loopback OR the
# configured tailnet bind IP. On failure: log + re-run bootstrap.sh.
# On success: exit 0 silently (job fires ~every 15 min; don't spam the log).
set -u

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
STATE_DIR="$HOME/.local/state/phone-agent"
LOG="$STATE_DIR/watchdog.log"
LOCK="$STATE_DIR/watchdog.lock"

probe() {  # $1 = ip; 0 iff HTTP 200 and body contains "ok"
    local body
    body=$(curl -sf --max-time 10 "http://$1:8462/health" 2>/dev/null) || return 1
    case "$body" in *ok*) return 0 ;; esac
    return 1
}

# Server binds the tailnet IP when the VPN is up (loopback then REFUSED),
# 0.0.0.0 when down — probe both. No jq dependency.
TS_IP=$(sed -n 's/.*"tailscale_ip"[^0-9]*\([0-9.]*\).*/\1/p' \
    "$HOME/.config/phone-agent/config.json" 2>/dev/null | head -1)

probe 127.0.0.1 && exit 0
[ -n "$TS_IP" ] && probe "$TS_IP" && exit 0

mkdir -p "$STATE_DIR"

# mkdir-based lock against concurrent runs; self-clears if older than 10 min
# (stale lock from a recovery run that itself got killed).
if ! mkdir "$LOCK" 2>/dev/null; then
    now=$(date +%s)
    age=$(( now - $(stat -c %Y "$LOCK" 2>/dev/null || echo "$now") ))
    [ "$age" -gt 600 ] || exit 0
    rmdir "$LOCK" 2>/dev/null || true
    mkdir "$LOCK" 2>/dev/null || exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

ts() { date '+%Y-%m-%dT%H:%M:%S%z'; }
echo "$(ts) health FAIL (127.0.0.1${TS_IP:+ + $TS_IP}) — re-running bootstrap.sh" >> "$LOG"
if bash "$SCRIPT_DIR/bootstrap.sh" >> "$LOG" 2>&1; then
    echo "$(ts) bootstrap.sh OK — service recovered" >> "$LOG"
else
    echo "$(ts) bootstrap.sh FAILED (exit $?)" >> "$LOG"
fi
