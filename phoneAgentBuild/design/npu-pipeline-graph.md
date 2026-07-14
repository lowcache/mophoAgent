# NPU Pipeline Graph Specification

## Architecture Overview

Three independent processing pipelines, each a directed acyclic graph (DAG) of stages. Each stage runs on the NPU or CPU as specified. Pipelines are triggered by the MCP capture tools and run asynchronously.

```
┌──────────────────────────────────────────────────┐
│                  Capture Tools                    │
│  phone.capture.audio →  phone.npu.transcribe      │
│  phone.capture.image →  phone.npu.ocr             │
│  phone.capture.share  →  phone.npu.classify       │
│  phone.capture.share  →  phone.npu.embed          │
└──────────────────────────────────────────────────┘
```

---

## Pipeline 1: Audio → Transcript

```
 audio.raw
    │
    ▼
┌─────────────┐
│   VAD Gate   │  NPU (always-on, <100mW) (NPU stretch; CPU baseline per D5)
│  slice into  │  filters out silence
│  speech segs │  outputs: segments with timestamps
└─────────────┘
    │
    ▼
┌─────────────┐
│  Diarization │  CPU (lightweight, speaker embedding)
│   (future)   │  assigns speaker labels to each segment
└─────────────┘
    │
    ▼
┌─────────────┐
│   Whisper    │  NPU (QNN backend, q4_0 quantized)
│  transcribe  │  model: whisper-small.en (~244M params)
└─────────────┘    TTFT: ~500ms for 5s audio
    │               throughput: ~2x realtime on NPU
    ▼
┌─────────────┐
│  Format +   │  CPU (lightweight post-processing)
│   Timestamp │  dedupe segments, correct punctuation
└─────────────┘    normalize whitespace
    │
    ▼
 ~/ingest/processed/transcripts/
  20260714_150322_transcript_a3f2c.json
```

### Output Format

```json
{
  "pipeline": "audio_transcript",
  "source": "~/ingest/audio/20260714_150322_raw.wav",
  "duration_sec": 14.2,
  "segments": [
    { "speaker": null, "start": 0.0, "end": 3.2, "text": "Reminder to check the flake update" },
    { "speaker": null, "start": 3.5, "end": 14.2, "text": "The net-gate microvm needs a route table update for the new Tailscale subnet." }
  ],
  "full_text": "Reminder to check the flake update. The net-gate microvm needs a route table update for the new Tailscale subnet.",
  "word_count": 23,
  "processing_time_ms": 4800
}
```

### VAD Parameters (tunable in config)

| Parameter | Default | Notes |
|---|---|---|
| `vad_threshold` | 0.5 | Silero VAD confidence threshold |
| `min_speech_duration_ms` | 250 | Shorter utterances merged |
| `min_silence_duration_ms` | 500 | Gap between speech segments |
| `speech_pad_ms` | 30 | Padding around detected speech |
| `window_size_ms` | 60 | VAD window size |

### Error States

- `VAD_TIMEOUT` — max_duration reached with no speech detected → delete raw audio, return empty
- `NPU_MODEL_FAIL` — whisper model failed to load → fall back to CPU (whisper.cpp on CPU, 2-3x slower)
- `AUDIO_CORRUPT` — WAV header invalid, zero-length file → return error, don't delete source for debugging

---

## Pipeline 2: Image → Text

```
 image.jpg
    │
    ▼
┌──────────────┐
│  Orientation  │  CPU (EXIF orientation correction + deskew)
│   Correct     │  auto-rotate based on EXIF metadata
└──────────────┘
    │
    ▼
┌──────────────┐
│  Layout Parse │  NPU (small detection model) (NPU stretch; CPU baseline per D5)
│   (future)    │  detect: text_blocks, tables, images, headings
└──────────────┘
    │
    ▼
┌──────────────┐
│     OCR       │  NPU (QNN backend)
│               │  model: custom ONNX → Qualcomm QNN compile
└──────────────┘    ~800ms for 1080p image
    │                languages: en default, configurable
    ▼
┌──────────────┐
│  Order +      │  CPU (reading order reconstruction)
│  Structure    │  sort blocks top-to-bottom, left-to-right
└──────────────┘    merge adjacent blocks by reading order
    │
    ▼
 ~/ingest/processed/ocr/
  20260714_150322_ocr_a3f2c.json
```

### Output Format

```json
{
  "pipeline": "image_ocr",
  "source": "~/ingest/images/20260714_150322_frame.jpg",
  "resolution": [1920, 1080],
  "blocks": [
    { "text": "Meeting Notes — 2026-07-14", "bbox": [50, 20, 400, 60], "confidence": 0.98, "type": "heading" },
    { "text": "Action items:\n1. Update flake lock\n2. Merge PR #47", "bbox": [50, 80, 600, 200], "confidence": 0.95, "type": "text" }
  ],
  "full_text": "Meeting Notes — 2026-07-14\nAction items:\n1. Update flake lock\n2. Merge PR #47",
  "word_count": 18,
  "processing_time_ms": 1200
}
```

### Error States

- `NO_TEXT_DETECTED` — OCR returned zero blocks → stage as "image (no text)" in case user wants it preserved as-is
- `NPU_MODEL_FAIL` → fall back to CPU OCR (tesseract in proot, 3-5x slower)
- `IMAGE_DECODE_FAIL` — corrupt file or unsupported format → return error

---

## Pipeline 3: Share → Extract → Summarize

```
 shared content (text | url | image | file)
    │
    ▼
┌──────────────┐
│   Classify    │  NPU (phone.npu.classify) (NPU stretch; CPU baseline per D5)
│  intent +     │  labels: store | query | command | ignore
│  content_type │  subtypes: article, code, note, link, question
└──────────────┘
    │
    ▼
┌──────────────┐
│   Extract     │  CPU
│               │  URL: fetch + readability extract
│               │  text: clean formatting + dedupe
│               │  image: route to pipeline 2
│               │  file: detect type, route accordingly
└──────────────┘
    │
    ▼
┌──────────────┐
│  Summarize    │  NPU (phone.npu.llm_infer, 1-3B model)
│   (optional)  │  only if content > 500 words
└──────────────┘    ~2-5s on NPU for 1000 words
    │
    ▼
┌──────────────┐
│   Embed       │  NPU (phone.npu.embed)
│               │  384-dim vector for future search
└──────────────┘
    │
    ▼
 ~/ingest/processed/summaries/
  20260714_150322_summary_a3f2c.json
```

### Output Format

```json
{
  "pipeline": "share_extract",
  "source": "https://example.com/article",
  "content_type": "article",
  "title": "How Nix Flakes Work",
  "extracted_text": "Nix flakes provide a reproducible way to manage dependencies...",
  "word_count": 1200,
  "summarized": true,
  "summary": "A guide to Nix flakes covering inputs, outputs, and lock files. Key takeaway: flakes make builds reproducible by pinning all inputs to content-addressed hashes.",
  "embedding": [0.0123, ...],
  "tags": ["nix", "flakes", "reproducible-builds"],
  "processing_time_ms": 4500
}
```

### Error States

- `FETCH_FAILED` — URL unreachable → store the URL raw
- `NON_TEXT_CONTENT` — shared file is binary (APK, PDF that can't be parsed) → store as-is, flag for manual review
- `CLASSIFY_LOW_CONFIDENCE` — confidence < 0.5 → route to `store` default, flag with user

---

## Pipeline Execution Model

All pipelines run asynchronously in a thread pool. The MCP capture tool returns immediately with the source path and a `pipeline_id`. The pipeline result is written to `~/ingest/processed/` when complete.

```python
class PipelineExecutor:
    pipelines: dict[str, Pipeline]
    thread_pool: ThreadPoolExecutor
    completion_callbacks: list[Callable]

    def submit(self, source_path: str, pipeline_name: str) -> str:
        pipeline_id = uuid4().hex[:8]
        future = self.thread_pool.submit(
            self.pipelines[pipeline_name].run, source_path
        )
        future.add_done_callback(lambda f: self._on_complete(pipeline_id, f))
        return pipeline_id

    def _on_complete(self, pipeline_id: str, future):
        result = future.result()  # or exception
        self.completion_callbacks.trigger(pipeline_id, result)
```

### Concurrency Limits

| Resource | Max concurrent | Reason |
|---|---|---|
| NPU inference | 1 | Single NPU on Snapdragon; queue serializes |
| CPU OCR (fallback) | 1 | Heavy CPU usage |
| VAD | 1 | Real-time audio, single mic channel |
| Network fetch | 3 | I/O bound, safe to parallelize |
| Embedding | 1 | Same NPU constraint |

### Queue Priority

NPU inference is serialized with a priority queue:

1. **Interactive** (Voice AI — sub-500ms target) → highest priority, preempts batch
2. **Scheduled** (Subconscious Scheduler tasks) → normal priority
3. **Batch** (ingest pipeline, background processing) → lowest priority, can be suspended for interactive
