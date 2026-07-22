---
from: claude-phone
to: claude-laptop
type: handoff
phase: 6
status: delivered
re: phase-6-voice-offline.md
---

# Phase-6 Voice AI + offline autonomy — delivered offline (tag `phone-mcp-phase-6`)

Built on the Phase-5/5.5 sign-off line (`ffa6269`). **Not deployed, not
live-verified** — offline evidence only; operator live-gate + your verify.sh
run pending.

## Shipped (6 tools → 27 total)
`phone.voice.{ask,start,stop}` + `phone.queue.{sync,deliver,clear_failed}`,
backed by three new packages:
- `voice/` — `tts.py` (termux-tts-speak, stdin-fed, media-stream volume),
  `router.py` (QueryRouter: classify → local-model | laptop-Ollama | system,
  httpx `/api/chat`, force_local), `session.py` (VoiceSession state machine:
  IDLE→TRANSCRIBING→ROUTING→SPEAKING, 30s per-substate timeout), `wake_word.py`
  (typed stub — see deferral 1).
- `msgqueue/` — `manager.py` (durable file-backed priority queue; atomic
  writes; retry_count persisted BEFORE the pending/failed move), `delivery.py`
  (ack-timeout retry protocol for the future push path).
- `offline/` — `detector.py` (D9 ladder: Ollama /api/version → ICMP laptop →
  ICMP 1.1.1.1), `mode.py` (LocalOnlyMode: force_local toggle + on_capture
  enqueue).
- Wiring in `tools/voice_common.py` + `tools/queue_common.py` (NPU-backed dep
  adapters over `get_queue().submit`, process-wide singletons).

## Design facts worth keeping
- **Package named `msgqueue/`, not `queue/`** (charter File Structure said
  `queue/`). A top-level `queue/` package shadows stdlib `queue`, which
  asyncio/anyio import. Tool names stay `phone.queue.*` and data stays under
  `~/ingest/queue/` per charter; only the Python package dir differs. (Same
  spirit as Phase-5's `rish_blocklist.txt`→`command_blocklist.txt` rename.)
- **Dependency injection over closures.** VoiceSession/QueryRouter/LocalOnlyMode
  take deps as ctor args; the NPU tools stay closures. `voice_common` adapts
  `get_queue().submit(...)` to the injected `infer/classify/transcribe` shapes.
  Router's `_classify` catches ANY classifier error and falls back to a keyword
  heuristic, so a cold/busy NPU never breaks routing.
- **1:1 extraction of `capture_audio`.** Body moved to module-level
  `record_and_trim(...)`; the registered `phone.capture.audio` tool now calls
  it. Behavior identical (test_geofence + stub-register unaffected); lets the
  voice session reuse the capture path without going through the MCP closure.
  This is the only edit to a previously signed-off file — please eyeball it.
- **Pull, not push.** `phone.queue.deliver` returns the item IN the RPC response
  (that IS the delivery) and acks pending→delivering→delivered; the phone never
  pushes. `clear_failed` does manual retry (retry_count→0) or delete.
- **Laptop identity via config.json** (`voice_common._laptop_config`): keys
  `laptop_host` / `laptop_ts_ip` / `ollama_model`, defaulting to the volnix
  tailnet IP so numeric curl+ping work pre-magic-DNS. Operator SHOULD set
  `laptop_host` to `volnix.<tailnet>.ts.net` (no-hardcoded-identity design note).

## Offline evidence (venv `/root/phone-agent/.venv`, LD_LIBRARY_PATH=$RUNTIME/lib)
- py_compile clean on all 20 new/touched modules.
- `tests/test_queue.py` — **8/8** (enqueue/dequeue/ack; fail persists
  retry_count before move; max_retries→failed; requeue resets to 0; discard;
  priority+age sort; type filter).
- `tests/test_router.py` — **6/6** (simple→local, complex+online→laptop via
  overridden `_query_ollama`, complex+offline→local_offline w/ `[offline` prefix,
  force_local never routes to laptop, heuristic path, system_handler).
- `tests/test_geofence.py` — 5/5 (regression after the capture extraction).
- stub-register (real FastMCP + register_all): **27 tools, no duplicates**, 6
  new tools present.
- `scripts/verify.sh` want-list + root README updated to 27.

## Deferrals (both charter-consistent — flagged, not hidden)
1. **Wake word is a typed stub.** `voice.start` returns WAKE_WORD_UNAVAILABLE
   until an OpenWakeWord ONNX model is operator-placed and a streaming mic
   source is wired. Charter: phase passes without wake word if `voice.ask` works.
2. **Auto-enqueue-on-offline is NOT wired.** Primitives exist
   (DisconnectionDetector, LocalOnlyMode.on_capture) and the queue tool surface
   is complete, but nothing automatically flips to local-only mode and enqueues
   captures when the laptop drops — that needs a background detection loop, which
   belongs to the Phase-7 subconscious scheduler. Operator concurred: deliver the
   surface now, wire auto-enqueue with the Phase-7 loop.

## Your gate
`scripts/verify.sh http://100.101.229.9:8462` → expect **5/5 @ 27** once the
operator deploys + bounces, plus an additive-diff review (esp. the capture_audio
extraction). Operator behavioral gate: `voice.ask {"text":"what is 2+2"}` speaks
via TTS (source local); `voice.ask {}` records→transcribes→routes→speaks;
`queue.sync/deliver/clear_failed` round-trip on a seeded item; complex query with
laptop reachable → source laptop, with laptop down → source local_offline.
