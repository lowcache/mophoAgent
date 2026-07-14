# Phase 6: Voice AI + Offline Autonomy

**Target Agent:** Claude Code (phone, Termux)
**Commit message:** `feat(phone-mcp): voice AI session + offline autonomy queue`

---

## What You Are Building

Two major subsystems in one phase:

1. **Voice AI** — An interactive voice session that: listens for wake word → captures audio → transcribes locally → routes to local model or laptop Ollama → speaks response via TTS. Runs as a session with state transitions (LISTENING → TRANSCRIBING → ROUTING → SPEAKING).

2. **Offline Autonomy Queue** — When the laptop is unreachable over Tailscale, the phone queues all outgoing items (voice queries, ingest manifests, scheduled task results) in a priority queue with delivery protocol, retry, dedup, and conflict resolution.

**Build order (risk-driven):** TTS → router → session with a *manual* trigger tool (`phone.voice.ask`) → wake word **last, experimental**. Continuous background mic access is the least reliable piece of the whole phone stack (and the mic is contended with `phone.capture.audio` — expect `MICROPHONE_BUSY` semantics). The phase is considered passing without wake word if the `phone.voice.ask` cycle works.

---

## Prerequisites

Phase 0 (server), Phase 1 (whisper + LLM), Phase 5 (notify). Tailscale must be configured between phone and laptop.

---

## File Structure

```
~/phone-agent/
├── voice/
│   ├── __init__.py
│   ├── session.py                 # NEW: voice session state machine
│   ├── wake_word.py               # NEW: wake word detector (experimental)
│   ├── tts.py                     # NEW: local TTS engine
│   ├── router.py                  # NEW: route query to local model vs laptop Ollama
├── queue/
│   ├── __init__.py
│   ├── manager.py                 # NEW: queue state machine
│   ├── delivery.py                # NEW: delivery protocol with retry + ack
├── offline/
│   ├── __init__.py
│   ├── detector.py                # NEW: disconnection mode detection
│   ├── mode.py                    # NEW: local-only mode behavior
├── tools/
│   ├── voice_ask.py               # NEW: phone.voice.ask (manual trigger)
│   ├── voice_start.py             # NEW: phone.voice.start
│   ├── voice_stop.py              # NEW: phone.voice.stop
│   ├── queue_sync.py              # NEW: phone.queue.sync
│   ├── queue_deliver.py           # NEW: phone.queue.deliver
│   ├── queue_clear_failed.py      # NEW: phone.queue.clear_failed
```

---

## Part A: Voice AI

### tts.py — Local TTS Engine (build FIRST)

Text-to-speech on the phone. Options (use first available):

**Option 1: Android TTS (TextToSpeech API)**
```python
# Via termux-tts-speak
subprocess.run(["termux-tts-speak", text, "-r", "1.0", "-p", "1.0"])
```
Simple, works, uses the system TTS engine (Google or Samsung).

**Option 2: Piper TTS (better quality, CPU)**
- https://github.com/rhasspy/piper-tts
- ONNX voices, ~100MB per voice, multiple languages
- Low latency (< 500ms for 20-word response)

**Option 3: espeak (fallback, robotic but fast)**
```bash
pkg install espeak
espeak "{text}"
```

### router.py — Query Router (build SECOND)

Decides whether to answer a query on the phone (fast path) or route to the laptop's Ollama (deep path). The laptop client is the **Ollama HTTP API over Tailscale** (`POST http://volnix.<tailnet>.ts.net:11434/api/chat`) per D3 — the phone never SSHes and never MCP-calls the laptop.

```python
class QueryRouter:
    def __init__(self, local_model, detector: DisconnectionDetector):
        self.local_model = local_model      # phone.npu.llm_infer path
        self.detector = detector            # D9 ladder (see Part B)
        self.ollama_url = "http://volnix.<tailnet>.ts.net:11434/api/chat"
        self.force_local = False            # set by LocalOnlyMode

    async def route(self, transcript: str) -> tuple[str, str]:
        """Returns (response, source); source ∈ local | laptop | local_offline."""
        classification = await classify_intent(transcript, labels=["simple", "complex", "system"])

        if classification.label == "system":
            # "lock laptop", "what's the battery" → handle locally
            return await self._handle_system(transcript), "local"

        online = (not self.force_local) and await self.detector.is_online()

        if classification.label == "complex" and online:
            response = await self._query_ollama(transcript)     # httpx POST /api/chat
            return response, "laptop"

        # simple queries, or complex while offline → local model
        response = await self.local_model.infer(transcript)
        if classification.label == "complex":
            return f"[offline, answered by phone model]\n{response}", "local_offline"
        return response, "local"
```

**Simple vs complex classification heuristic (fallback if classifier unavailable):**
- Length < 50 characters → likely simple
- Contains "what is", "who is", "hello", "hi" → likely simple
- Contains "code", "build", "why does", "debug", "review" → likely complex
- Contains system commands ("lock", "status", "notify") → system

### session.py — Voice AI Session State Machine (build THIRD)

```python
class VoiceSession:
    def __init__(self, whisper, router, tts, wake_word_detector=None):
        self.state = "IDLE"
        self.wake_word = wake_word_detector   # optional, experimental
        self.whisper = whisper
        self.router = router
        self.tts = tts

    async def ask(self, audio_path: str | None = None, text: str | None = None) -> dict:
        """Manual trigger path (phone.voice.ask): one full cycle, no wake word."""
        if text is None:
            if audio_path is None:
                audio_path = (await capture_audio(max_duration_sec=15))["audio_path"]
            self.state = "TRANSCRIBING"
            text = await self.whisper.transcribe(audio_path)
        self.state = "ROUTING"
        response, source = await self.router.route(text)
        self.state = "SPEAKING"
        await self.tts.speak(response)
        self.state = "IDLE"
        return {"response": response, "source": source}

    async def start(self):
        """Wake-word session (experimental). Enters LISTENING state."""
        self.state = "LISTENING"
        # wake_word.listen() runs in a dedicated thread; its callback hops
        # back onto the event loop via asyncio.run_coroutine_threadsafe
        self.wake_word.listen(self._on_wake_word_threadsafe)

    async def _on_wake_word(self):
        self.state = "LISTENING_ACTIVE"
        await self.ask()                      # same cycle as manual trigger
        self.state = "LISTENING"              # back to listening for next query

    def stop(self):
        self.state = "IDLE"
```

**States:**
- `IDLE` — Not listening. Wake word detection is off. (Power saving)
- `LISTENING` — Wake word detector active. No audio being captured yet.
- `LISTENING_ACTIVE` — Wake word detected. Capturing audio with VAD.
- `TRANSCRIBING` — Whisper is transcribing the captured audio.
- `ROUTING` — Transcribed text is being answered locally or by laptop Ollama.
- `SPEAKING` — TTS is playing the response.

**Timeouts:** If state stays in one sub-state for > 30s (e.g., TRANSCRIBING stuck), reset to IDLE and notify user.

### wake_word.py — Wake Word Detection (build LAST, experimental)

An always-on (when enabled) wake word detector.

**Approach 1: OpenWakeWord (recommended)**
- Small (~1MB) ONNX model trained on specific wake words, runs fine on CPU (NPU is a stretch goal per D5)
- Process 30ms audio frames, threshold > 0.5 for detection
- Customizable wake word (e.g., "Hey Phone", "Computer", "Hey Nexus")
- Training: https://github.com/dscripka/OpenWakeWord

**Approach 2: Porcupine (fallback)**
- Picovoice's Porcupine engine (free tier, on-device)
- Pre-trained wake words + custom training
- C library with Python bindings, CPU, <200μs per frame

```python
class WakeWordDetector:
    def __init__(self, model_path: str, sensitivity: float = 0.5):
        self.model = load_onnx_model(model_path)
        self.sensitivity = sensitivity

    def process_frame(self, audio_frame: np.ndarray) -> float:
        """Process a 30ms audio frame. Returns confidence 0.0-1.0."""
        result = self.model.run(None, {"input": audio_frame})
        return result[0][0]

    def listen(self, callback: Callable) -> None:
        """Runs in a dedicated thread. Requires a streaming mic source —
        the hard part on Termux; see Phase 2's optional pulseaudio note."""
        stream = open_mic_stream(sample_rate=16000, chunk_ms=30)
        for frame in stream:
            if self.process_frame(frame) > self.sensitivity:
                callback()
```

---

## Part B: Offline Autonomy

### offline/detector.py — Disconnection Mode Detection

There is **no `tailscale` CLI on the phone** (Android Tailscale is a VPN app). Detection is the D9 ladder:

```python
class DisconnectionDetector:
    def __init__(self, laptop_host: str = "volnix.<tailnet>.ts.net",
                 laptop_ts_ip: str = "100.x.x.x"):
        self.laptop_host = laptop_host
        self.laptop_ts_ip = laptop_ts_ip
        self.state = "ONLINE"  # ONLINE | DEGRADED | LAPTOP_UNREACHABLE | NO_INTERNET

    async def check_connection(self) -> str:
        # 1. Ollama answering → fully online
        if await self._curl_ok(f"http://{self.laptop_host}:11434/api/version", timeout=2):
            self.state = "ONLINE"
            return self.state

        # 2. Laptop pingable but Ollama down → degraded (route like offline)
        if await self._ping_ok(self.laptop_ts_ip):
            self.state = "DEGRADED"
            return self.state

        # 3. Internet works but laptop unreachable → laptop asleep OR tailnet
        #    down (indistinguishable without the tailscale CLI)
        if await self._ping_ok("1.1.1.1"):
            self.state = "LAPTOP_UNREACHABLE"
            return self.state

        # 4. Nothing works
        self.state = "NO_INTERNET"
        return self.state

    async def is_online(self) -> bool:
        return (await self.check_connection()) == "ONLINE"
```

**Reconnection polling:**
- ONLINE → check every 60s
- DEGRADED → check every 60s
- LAPTOP_UNREACHABLE → check every 60s (laptop wake cycles are slow)
- NO_INTERNET → check every 120s (user must usually act, e.g. airplane mode)

### queue/manager.py — Queue State Machine

```python
@dataclass
class QueueItem:
    id: str
    type: str  # "ingest", "voice_query", "schedule_result", "sensor_event"
    created_at: str  # ISO timestamp
    priority: int  # 0=high, 1=normal, 2=low
    payload: dict  # The actual data
    status: str  # "pending", "delivering", "delivered", "failed"
    retry_count: int = 0
    max_retries: int = 5
    resolved_locally: bool = False  # Voice query answered on phone
    deduplicated: bool = False  # Duplicate of already-processed item

class QueueManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pending_dir = base_dir / "queue" / "pending"
        self.delivering_dir = base_dir / "queue" / "delivering"
        self.delivered_dir = base_dir / "queue" / "delivered"
        self.failed_dir = base_dir / "queue" / "failed"

    async def enqueue(self, item: QueueItem):
        """Add an item to the pending queue."""
        path = self.pending_dir / f"{item.id}.json"
        path.write_text(json.dumps(asdict(item)))

    async def dequeue(self, item_id: str) -> QueueItem:
        """Move item from pending → delivering and return it."""
        src = self.pending_dir / f"{item_id}.json"
        dst = self.delivering_dir / f"{item_id}.json"
        src.rename(dst)
        return QueueItem(**json.loads(dst.read_text()))

    async def acknowledge(self, item_id: str):
        """Move item from delivering → delivered."""
        src = self.delivering_dir / f"{item_id}.json"
        dst = self.delivered_dir / f"{item_id}.json"
        src.rename(dst)

    async def fail(self, item_id: str):
        """Retry or park a failed delivery. CRITICAL: the incremented
        retry_count must be WRITTEN BACK to the JSON before the rename,
        otherwise retries loop forever."""
        src = self.delivering_dir / f"{item_id}.json"
        item = QueueItem(**json.loads(src.read_text()))
        item.retry_count += 1
        src.write_text(json.dumps(asdict(item)))          # persist the increment
        if item.retry_count >= item.max_retries:
            src.rename(self.failed_dir / f"{item_id}.json")
        else:
            src.rename(self.pending_dir / f"{item_id}.json")

    def list_pending(self, types: list[str] = None, limit: int = 50) -> list[QueueItem]:
        """List pending items, filtered by type, sorted by priority then age."""
        items = []
        for path in sorted(self.pending_dir.iterdir()):
            item = QueueItem(**json.loads(path.read_text()))
            if types and item.type not in types:
                continue
            items.append(item)
            if len(items) >= limit:
                break
        return sorted(items, key=lambda i: (i.priority, i.created_at))
```

**Ack timeout:** after `dequeue` moves an item to `delivering/`, if the laptop's acknowledgement doesn't arrive within 10s, call `fail(item_id)` — which persists the retry increment and moves it back to `pending/` (or `failed/` at max retries).

### offline/mode.py — Local-Only Mode

```python
class LocalOnlyMode:
    def __init__(self, queue_mgr: QueueManager, router: QueryRouter):
        self.queue = queue_mgr
        self.router = router
        self.active = False

    async def enter(self):
        """Switch to local-only mode."""
        self.active = True
        self.router.force_local = True  # All queries answered on the phone

    async def exit(self):
        """Return to normal mode. Sync queue."""
        self.active = False
        self.router.force_local = False
        await send_notification("Phone agent reconnected", "Syncing queued items")
        # The laptop agent will call phone.queue.sync when it sees the reconnection

    async def on_capture(self, capture_result: dict):
        """Enqueue ingest item for later delivery. (async — enqueue is awaited)"""
        item = QueueItem(
            id=generate_id(),
            type="ingest",
            created_at=timestamp(),
            priority=1,
            payload=capture_result,
            status="pending"
        )
        await self.queue.enqueue(item)
```

---

## Tools

### phone.voice.ask — One-Shot Voice Cycle (manual trigger)

```json
{ "input": { "text": "what's 2+2" },
  "output": { "response": "4", "source": "local" } }
```
Accepts `"text"` (skip capture+transcribe) or `"audio_path"` (transcribe then route) or neither (capture → transcribe → route → TTS).

### phone.voice.start — Start Voice AI Session (wake word, experimental)

```json
{ "input": { "wake_word": "hey phone" },
  "output": { "status": "listening", "session_id": "vs_a3f2c" } }
```

### phone.voice.stop — Stop Voice AI Session

```json
{ "input": {}, "output": { "status": "stopped" } }
```

### phone.queue.sync — List Pending Queue Items

```json
{ "input": { "types": ["ingest", "voice_query"], "limit": 50 },
  "output": {
    "pending_count": 5,
    "delivered_count": 10,
    "failed_count": 1,
    "items": [
      { "id": "vq_a3f2c", "type": "voice_query", "priority": 0, "summary": "...", "created_at": "..." }
    ]
  } }
```

### phone.queue.deliver — Deliver and Acknowledge

```json
{ "input": { "item_id": "vq_a3f2c", "acknowledge": true },
  "output": { "item": { }, "status": "delivered", "queue_remaining": 4 } }
```

### phone.queue.clear_failed — Clear Failed Items

```json
{ "input": { "item_id": "fi_xyz", "action": "retry" },
  "output": { "status": "retrying", "queue_remaining_failed": 0 } }
```

---

## Test Procedure

1. Test manual voice cycle FIRST:
   - `mcp_call phone.voice.ask '{"text":"what is 2+2"}'` → response spoken via TTS, source "local"
   - `mcp_call phone.voice.ask '{}'` → speak a question → transcribed → routed → spoken

2. Test wake word (experimental, only after 1 passes):
   - Call `phone.voice.start` with wake word
   - Say wake word → phone starts listening
   - Say "what's 2+2" → full cycle completes

3. Test offline detection:
   - Disconnect laptop from network (or stop Ollama)
   - Verify phone detects DEGRADED / LAPTOP_UNREACHABLE correctly
   - Make an ingest capture → verify it's queued

4. Test queue delivery:
   - Reconnect laptop
   - Call `phone.queue.sync` → verify pending items appear
   - Call `phone.queue.deliver` → verify item delivered
   - Call again → verify item no longer in pending

---

## Acceptance Criteria

- [ ] `phone.voice.ask` completes full cycle: (capture →) transcribe → route → TTS
- [ ] Simple queries answered locally in < 2s total (warm servers)
- [ ] Complex queries route to laptop Ollama when ONLINE, local with `[offline...]` disclaimer otherwise
- [ ] Offline detection distinguishes ONLINE / DEGRADED / LAPTOP_UNREACHABLE / NO_INTERNET
- [ ] Queue persists items across server restart (files on disk)
- [ ] Queue delivery with ack moves items from pending → delivered
- [ ] Failed items (max retries) moved to failed directory — retry_count visibly increments in the JSON
- [ ] Reconnection triggers sync notification
- [ ] (Experimental) wake word detection works (test 10 times, ≥ 8 detections) — not required to pass the phase

---

## Guardrails

- **Wake word detection is opt-in.** Off by default. User must explicitly call `phone.voice.start` to enable.
- **Voice AI has a 15s utterance cap.** Long monologues are cut at 15s. User can chain queries.
- **TTS volume respects phone's media volume.** Don't force volume up.
- **Queue does not auto-sync.** The laptop agent must explicitly call `phone.queue.sync`. The phone agent doesn't push.
- **Queue items are JSON on disk.** If the phone reboots, pending items survive in `~/ingest/queue/pending/`.
- **No cloud TTS.** All voice processing is local. termux-tts-speak uses the system TTS engine (Google's on-device TTS in Android).

---

## Git Commit

```bash
git add -A
git commit -m "feat(phone-mcp): voice AI session + offline autonomy queue"
git tag phone-mcp-phase-6
git push origin phone
```

Rollback: `git revert HEAD`. Voice AI + queue revert. Everything else continues working.
