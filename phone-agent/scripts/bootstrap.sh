#!/data/data/com.termux/files/usr/bin/bash
# phone-agent bootstrap (P0 + P3) — run ONCE natively: bash scripts/bootstrap.sh
# Idempotent. Installs packages, wires the runit service (termux-services) and
# Termux:Boot start script, enables + starts the service.
#
# Build-time env for the DEV side (proot), not needed here, recorded for P1:
#   PREFIX must be exported for Termux cmake under proot; UV_LINK_MODE=copy for
#   any uv operation touching the native venv; ggml builds need
#   -DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+i8mm.
set -euo pipefail

die() { echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] && die "running under proot/root — run in NATIVE Termux"
command -v pkg >/dev/null || die "pkg not found — not a native Termux shell?"

PREFIX=/data/data/com.termux/files/usr
AGENT="$HOME/mophoAgent/phone-agent"
SVDIR="$PREFIX/var/service/phone-agent"

[ -x "$AGENT/scripts/run.sh" ] || chmod +x "$AGENT/scripts/run.sh" 2>/dev/null \
    || die "run.sh missing at $AGENT/scripts/run.sh"

echo "==> stop any existing instance (hand-launched or supervised)"
# NEVER pkill -f here (matched our own shell once); scan /proc cmdlines instead.
sv down phone-agent 2>/dev/null || true

scan_pids() {  # pids whose cmdline matches $1, excluding this script
    for d in /proc/[0-9]*; do
        p=${d#/proc/}
        [ "$p" = "$$" ] && continue
        tr '\0' ' ' < "$d/cmdline" 2>/dev/null | grep -q "$1" && echo "$p"
    done
    return 0
}

kill_pat() {  # TERM, wait up to 10s, then KILL
    local pids; pids=$(scan_pids "$1")
    [ -z "$pids" ] && return 0
    echo "    stopping $1 (pid $pids)"
    kill $pids 2>/dev/null || true
    for _ in $(seq 1 10); do
        pids=$(scan_pids "$1")
        [ -z "$pids" ] && return 0
        sleep 1
    done
    echo "    TERM ignored, sending KILL to $pids"
    kill -9 $pids 2>/dev/null || true
}

kill_pat 'main\.py'        # MCP server (backends are its children)
kill_pat 'llama-server'    # stragglers, if any
kill_pat 'whisper-server'

for port in 8462 8463 8464 8465; do
    curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$port/health" \
        && die "port $port still in use after cleanup — investigate before re-running"
done

echo "==> pkg install (legitimizes the hand-extracted runtime, P3)"
pkg install -y termux-services termux-api llama-cpp \
    python-numpy python-pillow python-onnxruntime
# NOTE: whisper-cpp is NOT packaged in termux-main (checked 2026-07-16);
# whisper-server stays source-built in ~/phone-agent-runtime/bin.

echo "==> termux-api sanity (needs the Termux:API companion app)"
timeout 10 termux-battery-status >/dev/null \
    || echo "WARN: termux-api call failed — install/enable the Termux:API app"

echo "==> runit service dir: $SVDIR"
mkdir -p "$SVDIR/log"
cat > "$SVDIR/run" <<EOF
#!$PREFIX/bin/sh
exec 2>&1
exec $AGENT/scripts/run.sh
EOF
chmod +x "$SVDIR/run"
ln -sf "$PREFIX/share/termux-services/svlogger" "$SVDIR/log/run"

echo "==> Termux:Boot hook (~/.termux/boot/start-services.sh)"
mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/start-services.sh" <<EOF
#!$PREFIX/bin/sh
termux-wake-lock
. $PREFIX/etc/profile.d/start-services.sh
EOF
chmod +x "$HOME/.termux/boot/start-services.sh"

echo "==> start runsvdir + enable service"
# start-services.sh normally runs from a login shell; source it so a fresh
# termux-services install works without restarting Termux.
. "$PREFIX/etc/profile.d/start-services.sh" || true
sleep 2
sv-enable phone-agent 2>/dev/null || rm -f "$SVDIR/down"
sv up phone-agent

echo "==> waiting for /health 200 (backend model loads take ~30-60s)"
for _ in $(seq 1 36); do
    code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8462/health || true)
    [ "$code" = 200 ] && { echo "OK: phone-agent service is up"; exit 0; }
    sleep 5
done
echo "WARN: /health not 200 yet — check: sv status phone-agent ; tail $PREFIX/var/log/sv/phone-agent/current"
exit 1
