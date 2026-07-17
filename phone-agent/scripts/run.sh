#!/data/data/com.termux/files/usr/bin/bash
# phone-agent launcher (P1) — fast-fail, native-only.
# Called by the runit service ($PREFIX/var/service/phone-agent/run) and
# usable manually. Must NOT daemonize: runit supervises the foreground exec.
set -euo pipefail

die() { echo "FATAL: $*" >&2; exit 1; }

# P2 boundary: proot (fake uid 0) must never run the server.
[ "$(id -u)" -eq 0 ] && die "running under proot/root — launch from NATIVE Termux only"

# Termux:Boot runs with a minimal environment; make ours explicit.
PREFIX=/data/data/com.termux/files/usr
export HOME=/data/data/com.termux/files/home
# $HOME/bin carries rish (Shizuku) and the share hooks — capture tools
# resolve them via PATH.
export PATH="$HOME/bin:$PREFIX/bin:${PATH:-}"

AGENT="$HOME/mophoAgent/phone-agent"
RUNTIME="$HOME/phone-agent-runtime"

[ -x "$AGENT/.venv/bin/python" ] || die "venv python missing: $AGENT/.venv"
[ -f "$AGENT/main.py" ]          || die "main.py missing in $AGENT"
[ -d "$AGENT/models" ]           || die "models dir missing: $AGENT/models"

# Backends: llama-server may come from pkg ($PREFIX/bin) or the extracted
# runtime; whisper-server is not packaged in termux-main (checked 2026-07-16)
# and lives only in the runtime dir.
command -v llama-server >/dev/null || [ -x "$RUNTIME/bin/llama-server" ] \
    || die "llama-server not found (pkg install llama-cpp, or restore $RUNTIME/bin)"
[ -x "$RUNTIME/bin/whisper-server" ] \
    || die "whisper-server missing: $RUNTIME/bin (source-built; not in termux pkgs)"

# Known-good phase-1 config: runtime libs must be visible to the venv's
# onnxruntime and to runtime-dir backend binaries.
[ -d "$RUNTIME/lib" ] || die "runtime lib dir missing: $RUNTIME/lib"
export LD_LIBRARY_PATH="$RUNTIME/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

command -v termux-wake-lock >/dev/null && termux-wake-lock || true

cd "$AGENT"
exec .venv/bin/python main.py
