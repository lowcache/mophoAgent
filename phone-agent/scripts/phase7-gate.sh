#!/usr/bin/env bash
# Phase-7 operator gate — RUN FROM A NATIVE TERMUX SESSION (not proot).
#
#   1. deploy      (git pull --ff-only origin phone)         [--no-deploy to skip]
#   2. bounce      (sv restart phone-agent, wait for /health)[--no-bounce to skip]
#   3. verify.sh   (health / bad-bearer 401 / 32 tools / ping / embed)
#   4. behavioral  scheduler status -> start -> a 60s task actually FIRES ->
#                  condition gating skips a task -> add/remove persist ->
#                  stop. Result JSON lands in ~/ingest/processed/scheduled/.
#
# The firing check waits ~75s by design: the loop ticks every 30s and the
# probe task is on a 60s interval, so a fire needs up to two ticks.
#
# CANNOT be automated (do these by hand):
#   - the real 6h/daily/weekly tasks firing on their own schedule
#   - laptop-dependent tasks succeeding (needs laptop_host set + Ollama UP)
#   - the laptop's own verify.sh @ 32 + diff review
#
# Usage: scripts/phase7-gate.sh [BASE_URL] [--no-deploy] [--no-bounce]
set -uo pipefail

REPO="$HOME/mophoAgent"
AGENT="$HOME/phone-agent"
DEPLOY=1; BOUNCE=1; BASE=""
for a in "$@"; do
  case "$a" in
    --no-deploy) DEPLOY=0 ;;
    --no-bounce) BOUNCE=0 ;;
    http*)       BASE="$a" ;;
    *) echo "unknown arg: $a"; exit 2 ;;
  esac
done

FAIL=0
ok()   { echo "PASS  $1"; }
bad()  { echo "FAIL  $1"; FAIL=$((FAIL+1)); }
info() { echo "----  $1"; }

TOKEN=${PHONE_AGENT_TOKEN:-}
if [ -z "$TOKEN" ] && [ -f "$HOME/.config/phone-agent/token" ]; then
  TOKEN=$(tr -d '[:space:]' < "$HOME/.config/phone-agent/token" | sed $'1s/^\xEF\xBB\xBF//')
fi
[ -n "$TOKEN" ] || { echo "FATAL: no token (\$PHONE_AGENT_TOKEN or ~/.config/phone-agent/token)"; exit 2; }
command -v python3 >/dev/null || { echo "FATAL: python3 required"; exit 2; }

if [ -z "$BASE" ]; then
  TS_IP=$(sed -n 's/.*"tailscale_ip"[^0-9]*\([0-9.]*\).*/\1/p' \
      "$HOME/.config/phone-agent/config.json" 2>/dev/null | head -1)
  BASE="http://${TS_IP:-127.0.0.1}:8462"
fi
info "BASE=$BASE  deploy=$DEPLOY bounce=$BOUNCE"

call() {
  curl -s --max-time 120 -X POST "$BASE/mcp" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"$1\",\"arguments\":$2}}"
}

field() {
  python3 -c '
import json, sys
raw = sys.stdin.read()
try:
    r = json.loads(raw)["result"]
except Exception:
    print("__PARSE_ERROR__"); sys.exit()
d = r.get("structuredContent")
if not isinstance(d, dict):
    try:
        d = json.loads(r["content"][0]["text"])
    except Exception:
        d = {}
v = d.get(sys.argv[1], "")
print(v if not isinstance(v, (dict, list)) else json.dumps(v))
' "$1"
}

# task_field <task_id> <key>  — pull one field out of status().tasks[]
task_field() {
  python3 -c '
import json, sys
try:
    tasks = json.loads(sys.stdin.read())
except Exception:
    tasks = []
for t in tasks:
    if t.get("id") == sys.argv[1]:
        v = t.get(sys.argv[2], "")
        print(v if not isinstance(v, (dict, list)) else json.dumps(v))
        break
' "$1" "$2"
}

# --- 1. deploy ---
if [ "$DEPLOY" = 1 ]; then
  info "deploy: git -C $REPO pull --ff-only origin phone"
  git -C "$REPO" checkout phone >/dev/null 2>&1
  if git -C "$REPO" pull --ff-only origin phone; then ok "deploy pull"
  else bad "deploy pull (resolve manually, then rerun with --no-deploy)"; fi
  info "HEAD: $(git -C "$REPO" log --oneline -1)"
fi

# --- 2. bounce ---
if [ "$BOUNCE" = 1 ]; then
  info "bounce: sv restart phone-agent"
  if ! sv restart phone-agent 2>/dev/null; then
    if ! SVDIR="${PREFIX:-/data/data/com.termux/files/usr}/var/service" \
         sv restart phone-agent 2>/dev/null; then
      pid=$(ps -eo pid,args | awk '/[.]venv\/bin\/python main.py/{print $1}')
      if [ -n "$pid" ]; then info "sv unavailable; kill -TERM $pid (runit respawns)"; kill -TERM "$pid"; fi
    fi
  fi
  code=000
  for _ in $(seq 1 30); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$BASE/health" 2>/dev/null || echo 000)
    [ "$code" = 200 ] && break
    sleep 1
  done
  [ "$code" = 200 ] && ok "service healthy after bounce" || bad "service not healthy ($code) after 30s"
fi

# --- 3. verify.sh battery ---
info "verify.sh battery"
if "$AGENT/scripts/verify.sh" "$BASE"; then ok "verify.sh (incl. 32 tools)"
else bad "verify.sh battery (see lines above)"; fi

# --- 4. behavioral ---
info "check: scheduler.status loads the default task file"
resp=$(call phone.scheduler.status '{}')
cnt=$(printf '%s' "$resp" | field task_count)
rej=$(printf '%s' "$resp" | field rejected)
tasks=$(printf '%s' "$resp" | field tasks)
{ [ "$cnt" -ge 1 ] 2>/dev/null && ok "scheduler.status -> task_count=$cnt"; } \
  || bad "scheduler.status -> task_count=$cnt (expected the seeded defaults)"
[ "$rej" = "[]" ] && ok "no rejected task definitions" || bad "rejected task definitions: $rej"
nf=$(printf '%s' "$tasks" | task_field health_check next_fire)
[ -n "$nf" ] && ok "health_check next_fire=$nf" || bad "health_check has no next_fire"

info "check: add_task (60s probe task) persists and schedules"
resp=$(call phone.scheduler.add_task '{"id":"gate_probe","name":"Gate Probe","trigger":{"type":"interval","interval_seconds":60},"action":{"type":"shell","command":"echo gate_probe_ran"},"conditions":{},"notify_on":[]}')
tid=$(printf '%s' "$resp" | field task_id)
[ "$tid" = "gate_probe" ] && ok "add_task -> gate_probe scheduled" || bad "add_task -> $(printf '%s' "$resp" | field error) $tid"

info "check: add_task (skip probe) — battery_min_pct 200 can never be met"
call phone.scheduler.add_task '{"id":"gate_skip","name":"Gate Skip","trigger":{"type":"interval","interval_seconds":60},"action":{"type":"shell","command":"echo should_not_run"},"conditions":{"battery_min_pct":200},"notify_on":[]}' >/dev/null

info "check: scheduler.start"
resp=$(call phone.scheduler.start '{"reload":false}')
st=$(printf '%s' "$resp" | field status)
{ [ "$st" = "started" ] || [ "$st" = "already_running" ]; } && ok "scheduler.start -> $st" \
  || bad "scheduler.start -> status=$st err=$(printf '%s' "$resp" | field error)"

info "waiting up to 75s for the 60s probe task to fire (loop ticks every 30s)…"
fired=""; skipped=""
for _ in $(seq 1 15); do
  sleep 5
  tasks=$(call phone.scheduler.status '{}' | field tasks)
  fired=$(printf '%s' "$tasks" | task_field gate_probe last_result)
  skipped=$(printf '%s' "$tasks" | task_field gate_skip last_result)
  [ -n "$fired" ] && [ "$fired" != "None" ] && break
done
case "$fired" in
  *'"status": "success"'*) ok "gate_probe FIRED and succeeded: $fired" ;;
  "" |None)               bad "gate_probe never fired within 75s (loop not running?)" ;;
  *)                      bad "gate_probe fired but did not succeed: $fired" ;;
esac
case "$skipped" in
  *'"status": "skipped"'*) ok "gate_skip correctly SKIPPED on its battery condition" ;;
  ""|None)                 bad "gate_skip never evaluated" ;;
  *)                       bad "gate_skip should have been skipped: $skipped" ;;
esac

info "check: result JSON landed on disk"
n=$(ls -1 "$HOME/ingest/processed/scheduled/gate_probe-"*.json 2>/dev/null | wc -l)
{ [ "$n" -ge 1 ] 2>/dev/null && ok "durable log: $n gate_probe result file(s)"; } \
  || bad "no gate_probe result JSON in ~/ingest/processed/scheduled/"

info "check: remove_task + stop"
resp=$(call phone.scheduler.remove_task '{"task_id":"gate_probe"}')
[ "$(printf '%s' "$resp" | field removed)" = "True" ] && ok "remove_task -> gate_probe removed" \
  || bad "remove_task -> $(printf '%s' "$resp" | field error)"
call phone.scheduler.remove_task '{"task_id":"gate_skip"}' >/dev/null
resp=$(call phone.scheduler.stop '{}')
st=$(printf '%s' "$resp" | field status)
[ "$st" = "stopped" ] && ok "scheduler.stop -> stopped (ticks=$(printf '%s' "$resp" | field ticks))" \
  || bad "scheduler.stop -> status=$st"

info "check: removal persisted (status no longer lists the probes)"
tasks=$(call phone.scheduler.status '{}' | field tasks)
[ -z "$(printf '%s' "$tasks" | task_field gate_probe id)" ] && ok "gate_probe gone from the task table" \
  || bad "gate_probe still present after remove_task"

echo
if [ "$FAIL" -eq 0 ]; then echo "PHASE-7 GATE: ALL PASS ($BASE)"; else echo "PHASE-7 GATE: $FAIL FAILURE(S) ($BASE)"; fi
echo "MANUAL remaining: (1) set laptop_host in ~/.config/phone-agent/config.json to the LAPTOP's tailnet address — it currently defaults to the phone's own IP, so laptop-dependent tasks can never succeed  (2) leave the scheduler running and confirm health_check logs appear every 30min  (3) laptop: scripts/verify.sh $BASE"
exit "$FAIL"
