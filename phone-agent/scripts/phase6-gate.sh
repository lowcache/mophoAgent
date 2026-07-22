#!/usr/bin/env bash
# Phase-6 operator gate — RUN FROM A NATIVE TERMUX SESSION (not proot).
#
# Automates the deterministic gate:
#   1. deploy      (git pull --ff-only origin phone)         [--no-deploy to skip]
#   2. bounce      (sv restart phone-agent, wait for /health)[--no-bounce to skip]
#   3. verify.sh   (health / bad-bearer 401 / 27 tools / ping / embed)
#   4. behavioral  voice.ask text->local; voice.start->WAKE_WORD_UNAVAILABLE;
#                  voice.stop->stopped; queue seed->sync->deliver->sync;
#                  voice.ask complex-> reports laptop | local_offline
#   5. mic cycle   (interactive, ONLY with --mic: you speak, it transcribes)
#
# CANNOT be automated (do these by hand):
#   - whether the TTS was AUDIBLE (the tool only returns that it ran)
#   - seeing BOTH routing states — rerun once with laptop Ollama UP and once DOWN
#   - the laptop's own verify.sh @ 27 + diff review
#
# Usage: scripts/phase6-gate.sh [BASE_URL] [--no-deploy] [--no-bounce] [--mic]
#   BASE_URL default: config.json tailscale_ip, else http://127.0.0.1:8462
set -uo pipefail

REPO="$HOME/mophoAgent"
AGENT="$HOME/phone-agent"
DEPLOY=1; BOUNCE=1; MIC=0; BASE=""
for a in "$@"; do
  case "$a" in
    --no-deploy) DEPLOY=0 ;;
    --no-bounce) BOUNCE=0 ;;
    --mic)       MIC=1 ;;
    http*)       BASE="$a" ;;
    *) echo "unknown arg: $a"; exit 2 ;;
  esac
done

FAIL=0
ok()   { echo "PASS  $1"; }
bad()  { echo "FAIL  $1"; FAIL=$((FAIL+1)); }
info() { echo "----  $1"; }

# --- token + base (mirror verify.sh; also strip a UTF-8 BOM defensively) ---
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
info "BASE=$BASE  deploy=$DEPLOY bounce=$BOUNCE mic=$MIC"

call() {  # call <tool> <args-json> -> raw jsonrpc response on stdout
  curl -s --max-time 120 -X POST "$BASE/mcp" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"$1\",\"arguments\":$2}}"
}

field() {  # field <key>   (reads a jsonrpc response on stdin, prints tool-dict[key])
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

# --- 3. verify.sh battery (health / 401 / 27 tools / ping / embed) ---
info "verify.sh battery"
if "$AGENT/scripts/verify.sh" "$BASE"; then ok "verify.sh (incl. 27 tools)"
else bad "verify.sh battery (see lines above)"; fi

# --- 4. behavioral ---
# The FIRST inference after a bounce cold-loads the lazy qwen LLM backend
# (:8463): that call alone can take ~30-60s and LOOKS hung but isn't. Warm it
# first so the checks below are quick, and breadcrumb each step so any pause is
# attributable rather than mistaken for a hang.
info "warming local LLM (cold-load after a bounce can take ~60s — this is normal)…"
call phone.npu.llm_infer '{"prompt":"hi","max_tokens":1}' >/dev/null 2>&1 || true

info "check: voice.ask (text -> local) — speaks via TTS"
resp=$(call phone.voice.ask '{"text":"what is two plus two"}')
src=$(printf '%s' "$resp" | field source)
err=$(printf '%s' "$resp" | field error)
ans=$(printf '%s' "$resp" | field response)
if [ "$src" = "local" ] && [ -z "$err" ] && [ -n "$ans" ]; then
  ok "voice.ask text -> source=local, response=\"$ans\"  (listen: TTS should have spoken it)"
else bad "voice.ask text (source=$src err=$err response=\"$ans\")"; fi

info "check: voice.start / voice.stop"
resp=$(call phone.voice.start '{}')
err=$(printf '%s' "$resp" | field error)
[ "$err" = "WAKE_WORD_UNAVAILABLE" ] && ok "voice.start -> WAKE_WORD_UNAVAILABLE (by design)" \
  || bad "voice.start -> err=$err (expected WAKE_WORD_UNAVAILABLE)"

resp=$(call phone.voice.stop '{}')
st=$(printf '%s' "$resp" | field status)
[ "$st" = "stopped" ] && ok "voice.stop -> stopped" || bad "voice.stop -> status=$st"

info "check: queue seed -> sync -> deliver -> sync"
# queue round-trip (no enqueue tool yet — auto-enqueue is the Phase-7 deferral)
iid=$(python3 - <<'PY'
import json, os, secrets, time
d = os.path.expanduser("~/ingest/queue/pending"); os.makedirs(d, exist_ok=True)
iid = "vq_%s" % secrets.token_hex(4)
json.dump({"id": iid, "type": "voice_query",
           "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "priority": 0, "payload": {"summary": "gate seed"}, "status": "pending",
           "retry_count": 0, "max_retries": 5, "resolved_locally": False,
           "deduplicated": False}, open(os.path.join(d, iid + ".json"), "w"))
print(iid)
PY
)
resp=$(call phone.queue.sync '{}')
pc=$(printf '%s' "$resp" | field pending_count)
{ [ "$pc" -ge 1 ] 2>/dev/null && ok "queue.sync -> pending_count=$pc"; } || bad "queue.sync -> pending_count=$pc"
resp=$(call phone.queue.deliver "{\"item_id\":\"$iid\"}")
st=$(printf '%s' "$resp" | field status)
[ "$st" = "delivered" ] && ok "queue.deliver -> delivered" || bad "queue.deliver -> status=$st"
resp=$(call phone.queue.sync '{}')
dc=$(printf '%s' "$resp" | field delivered_count)
{ [ "$dc" -ge 1 ] 2>/dev/null && ok "queue.sync -> delivered_count=$dc"; } || bad "queue.sync -> delivered_count=$dc"

info "check: voice.ask (complex -> laptop | local_offline) — speaks a short preview"
resp=$(call phone.voice.ask '{"text":"debug why my build fails and explain the fix"}')
src=$(printf '%s' "$resp" | field source)
case "$src" in
  laptop)        ok "voice.ask complex -> source=laptop (Ollama reached)" ;;
  local_offline) ok "voice.ask complex -> source=local_offline (laptop/Ollama unreachable — expected if down)" ;;
  *)             bad "voice.ask complex -> unexpected source=$src" ;;
esac

# --- 5. mic cycle (interactive) ---
if [ "$MIC" = 1 ]; then
  info "MIC CYCLE — press Enter, then speak a short question; recording runs ~15s"
  read -r _ || true
  resp=$(call phone.voice.ask '{}')
  tr=$(printf '%s' "$resp" | field transcript)
  src=$(printf '%s' "$resp" | field source)
  err=$(printf '%s' "$resp" | field error)
  if [ -z "$err" ] && [ -n "$tr" ]; then ok "voice.ask mic cycle -> transcript=\"$tr\" source=$src"
  else bad "voice.ask mic cycle (err=$err transcript=\"$tr\")"; fi
else
  info "mic cycle SKIPPED (pass --mic to run it interactively)"
fi

echo
if [ "$FAIL" -eq 0 ]; then echo "PHASE-6 GATE: ALL PASS ($BASE)"; else echo "PHASE-6 GATE: $FAIL FAILURE(S) ($BASE)"; fi
echo "MANUAL remaining: (1) did you HEAR the TTS?  (2) rerun with Ollama UP and DOWN for both routes  (3) laptop: scripts/verify.sh $BASE"
exit "$FAIL"
