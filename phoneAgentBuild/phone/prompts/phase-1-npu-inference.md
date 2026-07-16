# Phase 1: CPU-baseline inference layer with NPU stretch (D5)

**Target Agent:** Claude Code (phone, Termux)
**Commit message:** `feat(phone-mcp): NPU inference — whisper, ocr, embed, classify`

---

## What You Are Building

The inference runtime for the CPU baseline with NPU stretch (D5). Loads models into memory, runs inference requests through a serialized priority queue (only one inference at any time), and returns results. Four compute tools become functional.

---

## Prerequisites

Phase 0 is fully built, tested, and committed. The MCP server skeleton is running in Termux.

---

## File Structure

```
~/phone-agent/
├── main.py                          # ← from Phase 0 (modified: register new tools)
├── tool_registry.py                 # ← from Phase 0 (modified: async dispatch)
├── tools/
│   ├── __init__.py
│   ├── health.py                    # ← from Phase 0
│   ├── transcribe.py                # NEW: phone.npu.transcribe
│   ├── ocr.py                       # NEW: phone.npu.ocr
│   ├── embed.py                     # NEW: phone.npu.embed
│   ├── classify.py                  # NEW: phone.npu.classify
│   ├── infer.py                     # NEW: phone.npu.llm_infer
├── npu/
│   ├── __init__.py
│   ├── bridge.py                    # NEW: NPU runtime singleton
│   ├── models.py                    # NEW: model registry + lifecycle
│   ├── queue.py                     # NEW: priority inference queue
├── config/
│   ├── __init__.py
│   ├── settings.py                 # ← from Phase 0 (modified: add model paths)
├── pyproject.toml                   # ← from Phase 0 (modified: add deps)
├── models/                          # NEW: model files go here
│   ├── whisper-small.en-q4_0.gguf   # Whisper quant
│   ├── ocr-model.onnx               # OCR model
│   └── all-minilm-l6-v2-q4.gguf     # Embedding model
├── ingest/                          # NEW: created by server on startup
│   └── .gitkeep                     # Placeholder (ingest structure built in Phase 2)
```

---

## Implementation Spec

### npu/models.py — Model Registry

Each model has a registration entry:

```python
@dataclass
class ModelSpec:
    name: str                          # e.g. "whisper-small.en"
    path: Path                         # Path to model file
    kind: Literal["whisper", "ocr", "embed", "classify", "llm"]
    quant: str                         # e.g. "q4_0", "fp16", "int8"
    max_context: int                   # Max tokens or audio length in seconds
    load_on_start: bool                # Load eagerly (true for whisper, embed) or lazy
    memory_estimate_mb: int            # Estimated RAM/VRAM footprint
    backend: Literal["qnn", "llama.cpp", "onnx"]  # Which runtime engine
```

Predefined models:

| Name | Kind | max_context | load_on_start | mem_est | backend |
|---|---|---|---|---|---|
| whisper-small.en-q4_0 | whisper | 30s audio | true | 512 | whisper.cpp (server mode) |
| ocr-model | ocr | 4096px | false | 256 | onnxruntime (CPU EP; QNN EP stretch) |
| all-minilm-l6-v2-q4 | embed | 256 tokens | true | 128 | llama.cpp llama-server |
| qwen2.5-1.5b-q4 | classify | 1024 tokens | false | 2048 | llama.cpp llama-server |
| qwen2.5-1.5b-q4 | llm | 1024 tokens | false | 2048 | llama.cpp llama-server |

Model lifecycle:
- `load(model_name)` — Load model into NPU memory. Blocks if another model is loading.
- `unload(model_name)` — Unload from NPU memory. Called when queue is idle >30s for lazy models.
- `is_loaded(model_name)` → bool
- `loaded_models()` → list of loaded model names

### npu/queue.py — Priority Inference Queue

Only one NPU inference runs at a time. This queue serializes concurrent requests.

```python
from dataclasses import dataclass, field
import asyncio
import time

@dataclass(order=True)
class InferenceRequest:
    priority: int
    timestamp: float
    model: str = field(compare=False)
    input: Any = field(compare=False)
    future: asyncio.Future = field(compare=False)

class InferenceQueue:
    def __init__(self, bridge: NPUBridge):
        self.queue = asyncio.PriorityQueue()
        self.bridge = bridge
        # Note: asyncio.PriorityQueue + create_task needs a running loop
        # (create _worker_task in server startup hook)

    async def submit(self, model: str, input: Any, priority: int = 2) -> Any:
        future = asyncio.get_event_loop().create_future()
        request = InferenceRequest(priority, time.time(), model, input, future)
        await self.queue.put(request)
        return await future

    async def _worker_loop(self):
        while True:
            request = await self.queue.get()
            try:
                result = await self.bridge.infer(request.model, request.input)
                request.future.set_result(result)
            except Exception as e:
                request.future.set_exception(e)
```

Priority values:
- `0` (interactive) — Voice AI queries. Preempts currently running work if possible.
- `1` (scheduled) — Subconscious scheduler tasks.
- `2` (batch) — Ingest pipeline processing. Lowest priority, get queued behind everything.

**Preemption:** A running batch job may be cancelled and requeued from scratch to allow interactive orders ahead of pending work (no suspend/resume per D8).

### npu/bridge.py — NPU Runtime

```python
import httpx
import asyncio

class NPUBridge:
    def __init__(self, models: ModelRegistry):
        self.models = models
        # Manages persistent child processes, restarts on crash
        # llama-server on 127.0.0.1:8463 for LLM+classify
        # llama-server --embedding on :8464
        # whisper-server on :8465

    async def infer(self, model_name: str, input: Any) -> dict:
        model = self.models.get(model_name)
        if not model:
            raise ValueError(f"Unknown model: {model_name}")
        if not self.models.is_loaded(model_name):
            await self.models.load(model_name)

        # Route to the correct backend
        if model.kind == "whisper":
            return await self._whisper_infer(model, input)  # audio → segments
        elif model.kind == "ocr":
            return await self._ocr_infer(model, input)      # image → text blocks
        elif model.kind == "embed":
            return await self._embed_infer(model, input)    # text → vector
        elif model.kind == "classify":
            return await self._classify_infer(model, input) # text → label
        elif model.kind == "llm":
            return await self._llm_infer(model, input)      # prompt → text
```

#### Whisper Backend (`_whisper_infer`)

Uses HTTP calls to the persistent `whisper-server` (`/inference`).

```python
async def _whisper_infer(self, model: ModelSpec, input: dict) -> dict:
    # input: { "audio_path": str, "language": "en", "temperature": 0.0 }
    # output: { "segments": [...], "full_text": "...", "processing_time_ms": 1234, "model_used": "..." }
```

#### OCR Backend (`_ocr_infer`)

Uses ONNX Runtime (CPU EP; QNN EP stretch).

```python
async def _ocr_infer(self, model: ModelSpec, input: dict) -> dict:
    # input: { "image_path": str, "languages": ["en"] }
    # output: { "blocks": [{"text": str, "bbox": [x1,y1,x2,y2], "confidence": float}], "full_text": "...", "processing_time_ms": 1234 }
```

Implementation:
- Load image with PIL, preprocess (deskew, grayscale, threshold)
- Run ONNX model via `onnxruntime.InferenceSession`
- Post-process output (CTC decoder) to produce text blocks
- Sort blocks by reading order (top-left first)

#### Embedding Backend (`_embed_infer`)

Uses HTTP calls to `llama-server --embedding` (`/v1/embeddings`).

```python
async def _embed_infer(self, model: ModelSpec, input: dict) -> dict:
    # input: { "text": str, "normalize": true }
    # output: { "embedding": [float, ...], "dimensions": 384, "processing_time_ms": 45 }
```

#### Classify Backend (`_classify_infer`)

Uses HTTP calls to `llama-server` (`/v1/chat/completions`) with constrained prompt + logprobs (`n_probs`) for confidence per D4.

```python
async def _classify_infer(self, model: ModelSpec, input: dict) -> dict:
    # input: { "text": str, "labels": ["store", "query", "command", "ignore"] }
    # output: { "label": str, "confidence": float, "scores": {label: score} }
```

#### LLM Inference Backend (`_llm_infer`)

The fast-path small model inference for local NPU responses.

```python
async def _llm_infer(self, model: ModelSpec, input: dict) -> dict:
    # input: { "prompt": str, "max_tokens": 256, "temperature": 0.7 }
    # output: { "response": str, "tokens_generated": int, "ttft_ms": int, "tokens_per_sec": float, "model_used": str, "routed_to_laptop": false }
```

Implementation:
- HTTP call to `llama-server` (`/v1/chat/completions`)
- Parse the generated text
- Measure TTFT (time to first token) and throughput

### Tools

Each tool handler reads its input, validates it with Pydantic, submits to the inference queue with the correct priority, formats the output, and returns it.

**Priority mapping for tools:**
- `phone.npu.transcribe` — priority 1 (background, but user is waiting)
- `phone.npu.ocr` — priority 1
- `phone.npu.embed` — priority 2 (batch)
- `phone.npu.classify` — priority 0 (interactive, blocks routing)
- `phone.npu.llm_infer` — priority 0 (interactive)

### Tool Registration

Add all 5 tools to the tool registry's tool list. Each tool must define its input schema and output format in the tool metadata.

---

## Model File Sources

Models are NOT committed to the repo. They're downloaded separately:

```bash
# Create models directory
mkdir -p ~/phone-agent/models/

# Whisper small.en (q4_0)
wget -O ~/phone-agent/models/whisper-small.en-q4_0.gguf \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en-q4_0.bin

# Embedding model
wget -O ~/phone-agent/models/all-minilm-l6-v2-q4.gguf \
  https://huggingface.co/ChristianAzinn/ggml-all-MiniLM-L6-v2-q4_0/resolve/main/ggml-model-q4_0.gguf

# OCR model
# TODO: CPU ONNX OCR model (e.g. PaddleOCR onnx export); QNN compile is stretch
```

---

## Test Procedure

1. Start the server:
   ```bash
   cd ~/phone-agent && python main.py
   ```

2. Test transcribe with a test WAV file:
   ```bash
   # Record a test file
   termux-microphone-record -d 5 -f /tmp/test.wav

   # Send transcribe request
   echo '{"jsonrpc":"2.0","method":"tools/call","id":3,"params":{"name":"phone.npu.transcribe","arguments":{"audio_path":"/tmp/test.wav","language":"en"}}}' | ...
   ```

3. Expected for transcribe (5s audio):
   ```json
   {"jsonrpc":"2.0","id":3,"result":{"segments":[{"start_sec":0.0,"end_sec":5.0,"text":"..."}],"full_text":"...","processing_time_ms":<5000,"model_used":"whisper-small.en-q4_0"}}
   ```

4. Test embed:
   ```bash
   echo '{"jsonrpc":"2.0","method":"tools/call","id":4,"params":{"name":"phone.npu.embed","arguments":{"text":"Hello world","normalize":true}}}' | ...
   ```
   Expected: 384-dimensional float array in under 100ms.

5. Test priority preemption: Submit a long batch inference, then immediately submit an interactive one. Verify interactive completes first.

---

## Acceptance Criteria

- [ ] All 5 NPU tools return correct output formats
- [ ] Whisper transcribes 10s audio in < 10s on CPU (< 5s NPU stretch)
- [ ] Embedding returns 384-dim vector in < 300ms
- [ ] Classifier returns correct label with confidence > 0.8
- [ ] LLM inference starts generating in < 1s warm (TTFT)
- [ ] Priority queue: interactive (0) runs before batch (2)
- [ ] Cancelled batch request is requeued and completes after interactive
- [ ] Model unloading after 30s idle (lazy-loaded models only)
- [ ] Error handling: `MODEL_NOT_LOADED`, `NPU_BUSY`, `AUDIO_TOO_LONG`
- [ ] Server starts successfully with all models loaded

---

## Guardrails

- **No capture tools yet.** NPU inference works on files that already exist in the filesystem. Audio/image capture comes in Phase 2.
- **No ingest directory writes beyond creating `~/ingest/.gitkeep`.** Phase 3 builds on this.
- **Models are downloaded, not committed.**
- **Priority queue enforces single NPU inference.** If you can't make QNN run concurrent inference, don't try — use the queue.
- **QNN is the primary backend.** If QNN isn't available for a specific model, fall back to CPU with a performance warning logged to stderr. The tool handler marks `"backend": "cpu_fallback"` in the response.
- **All inference is async.** The tool handler submits to the queue and awaits the future. No blocking the dispatch loop.
- **Measure and report `processing_time_ms`** in every response. This data feeds into the Compute Auditor (future phase) for baseline monitoring.

---

## Dependencies to Add in pyproject.toml

```toml
dependencies = [
    "httpx",
    "pydantic>=2.0",
    "Pillow>=10.0",           # Image preprocessing for OCR
    "numpy>=1.26",
    "onnxruntime>=1.18",      # For OCR model (note: install from tur-repo if pip wheel unavailable)
]
```

**System dependencies (install via pkg):**
```bash
pkg install python numpy openblas llama-cpp || echo "llama-cpp not in pkg, building from source"
# Explicit note per D5: no QNN backend exists in mainline, build with plain CPU flags on Termux.
```

---

## Git Commit

```bash
git add -A
git commit -m "feat(phone-mcp): NPU inference — whisper, ocr, embed, classify"
git tag phone-mcp-phase-1
git push origin phone
```

Rollback: `git revert HEAD`. All 5 tools disappear. Phase 0 skeleton still works.
