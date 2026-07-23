#!/usr/bin/env bash
# phone-agent pre-merge verify battery (P4).
# Run from any host that can reach the server (laptop over tailnet, or
# loopback on-device):  scripts/verify.sh [BASE_URL]
#   default BASE_URL: http://127.0.0.1:8462
#   tailnet from volnix: scripts/verify.sh http://100.101.229.9:8462
# Token: $PHONE_AGENT_TOKEN, else ~/.config/phone-agent/token.
# Exit 0 = all green (merge allowed); nonzero = red battery, no merge.
set -uo pipefail

if [ $# -ge 1 ]; then
    BASE=$1
else
    # On-device default: the server binds the configured tailnet IP when the
    # VPN is up (loopback refused), 0.0.0.0 when down — prefer the config IP.
    TS_IP=$(sed -n 's/.*"tailscale_ip"[^0-9]*\([0-9.]*\).*/\1/p' \
        "$HOME/.config/phone-agent/config.json" 2>/dev/null | head -1)
    BASE="http://${TS_IP:-127.0.0.1}:8462"
fi
TOKEN=${PHONE_AGENT_TOKEN:-}
[ -z "$TOKEN" ] && [ -f "$HOME/.config/phone-agent/token" ] \
    && TOKEN=$(tr -d '[:space:]' < "$HOME/.config/phone-agent/token")
[ -n "$TOKEN" ] || { echo "FATAL: no token (\$PHONE_AGENT_TOKEN or ~/.config/phone-agent/token)"; exit 2; }
command -v python3 >/dev/null || { echo "FATAL: python3 required"; exit 2; }

FAIL=0
ok()  { echo "PASS  $1"; }
bad() { echo "FAIL  $1"; FAIL=$((FAIL+1)); }

rpc() {  # rpc <id> <method> <params-json>
    curl -s --max-time 120 -X POST "$BASE/mcp" \
        -H "Authorization: Bearer $TOKEN" \
        -H 'Content-Type: application/json' \
        -H 'Accept: application/json, text/event-stream' \
        -d "{\"jsonrpc\":\"2.0\",\"id\":$1,\"method\":\"$2\",\"params\":$3}"
}

# 1 — health (no auth)
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$BASE/health" || echo 000)
[ "$code" = 200 ] && ok "GET /health -> 200" || bad "GET /health -> $code (want 200)"

# 2 — bad bearer rejected
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -X POST "$BASE/mcp" \
    -H 'Authorization: Bearer bad' -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -d '{"jsonrpc":"2.0","id":0,"method":"tools/list","params":{}}' || echo 000)
[ "$code" = 401 ] && ok "bad bearer -> 401" || bad "bad bearer -> $code (want 401)"

# 3 — tools/list: exact phase-1+2+3+4+5+6 tool set
rpc 1 tools/list '{}' | python3 -c '
import json, sys
want = sorted(["phone.system.ping", "phone.system.state",
               "phone.npu.transcribe", "phone.npu.ocr", "phone.npu.embed",
               "phone.npu.classify", "phone.npu.llm_infer",
               "phone.capture.audio", "phone.capture.image",
               "phone.capture.screenshot", "phone.capture.share",
               "phone.pipeline.run",
               "phone.sensor.read_imu", "phone.sensor.read_modem",
               "phone.sensor.read_gps", "phone.sensor.read_light",
               "phone.sensor.read_proximity",
               "phone.system.rish", "phone.system.termux_exec",
               "phone.system.free_ram", "phone.system.notify",
               "phone.voice.ask", "phone.voice.start", "phone.voice.stop",
               "phone.queue.sync", "phone.queue.deliver",
               "phone.queue.clear_failed",
               "phone.scheduler.start", "phone.scheduler.stop",
               "phone.scheduler.status", "phone.scheduler.add_task",
               "phone.scheduler.remove_task"])
got = sorted(t["name"] for t in json.load(sys.stdin)["result"]["tools"])
sys.exit(0 if got == want else print(f"got {got}") or 1)
' && ok "tools/list -> expected 32 tools" || bad "tools/list mismatch"

# 4 — ping round-trip
rpc 2 tools/call '{"name":"phone.system.ping","arguments":{}}' | python3 -c '
import json, sys
r = json.load(sys.stdin)["result"]
sys.exit(1 if r.get("isError") else 0)
' && ok "phone.system.ping" || bad "phone.system.ping errored"

# 5 — embed: 384-dim, unit norm
rpc 3 tools/call '{"name":"phone.npu.embed","arguments":{"text":"verify battery"}}' | python3 -c '
import json, math, sys
r = json.load(sys.stdin)["result"]
v = json.loads(r["content"][0]["text"])["embedding"]
n = math.sqrt(sum(x * x for x in v))
assert len(v) == 384, f"dim {len(v)}"
assert abs(n - 1.0) < 0.01, f"norm {n}"
' && ok "phone.npu.embed -> 384-dim, norm ~1.0" || bad "phone.npu.embed shape/norm"

echo
if [ "$FAIL" -eq 0 ]; then echo "VERIFY: ALL PASS ($BASE)"; else echo "VERIFY: $FAIL FAILURE(S) ($BASE)"; fi
exit "$FAIL"
