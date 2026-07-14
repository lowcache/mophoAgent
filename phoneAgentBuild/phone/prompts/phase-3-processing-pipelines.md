# Phase 3: Processing Pipelines

**Target Agent:** Claude Code (phone, Termux)
**Commit message:** `feat(phone-mcp): processing pipelines — audio→text, image→ocr, share→extract`

---

## What You Are Building

Three DAG pipelines that chain capture tools + compute tools into end-to-end transforms. When a capture completes, a pipeline is triggered automatically. Output lands as structured JSON in `~/ingest/processed/`.

---

## Prerequisites

Phases 0 + 1 + 2 built, tested, committed. Capture tools create raw files. Compute tools process them. This phase chains them together.

---

## File Structure

```
~/phone-agent/
├── pipeline/
│   ├── __init__.py
│   ├── executor.py                 # NEW: async DAG stage runner
│   ├── audio_transcript.py         # NEW: Pipeline 1
│   ├── image_ocr.py                # NEW: Pipeline 2
│   ├── share_extract.py            # NEW: Pipeline 3
│   ├── format.py                   # NEW: output formatters
├── ingest/
│   ├── capture_trigger.py          # NEW: auto-start pipeline on capture
├── tools/
│   ├── pipeline_trigger.py         # NEW: manual pipeline trigger tool
```

---

## Implementation Spec

### pipeline/executor.py — DAG Executor

An async stage runner. NPU/LLM stages await the inference queue directly; CPU-bound stages run via `asyncio.to_thread` so they never block the event loop.

```python
@dataclass
class Stage:
    name: str
    fn: Callable                      # async def(**inputs) -> dict
    inputs: list[str]                 # Keys from the pipeline context this stage reads
    outputs: list[str]                # Keys this stage writes to the pipeline context
    npu_required: bool = False        # Does this stage go through the inference queue?
    timeout_sec: int = 60

@dataclass
class Pipeline:
    name: str
    stages: list[Stage]
    output_type: str                  # "transcript", "ocr", "summary"

class MissingInput(Exception): ...

class PipelineExecutor:
    def __init__(self, npu_queue: InferenceQueue):
        self.pipelines: dict[str, Pipeline] = {}
        self.npu_queue = npu_queue

    def register(self, pipeline: Pipeline):
        self.pipelines[pipeline.name] = pipeline

    async def run(self, pipeline_name: str, context: dict) -> dict:
        """Run a pipeline with the given context. Context contains source file paths."""
        pipeline = self.pipelines[pipeline_name]
        run_context = dict(context)   # mutable per-pipeline run

        for stage in pipeline.stages:
            stage_input = {}
            for key in stage.inputs:
                if key not in run_context:
                    raise MissingInput(f"{pipeline_name}/{stage.name}: missing '{key}'")
                stage_input[key] = run_context[key]

            # NPU stages await the serialized inference queue; CPU stages
            # run in a worker thread. Both are bounded by the stage timeout.
            coro = stage.fn(**stage_input) if stage.npu_required \
                else asyncio.to_thread(stage.fn_sync, **stage_input)
            try:
                result = await asyncio.wait_for(coro, timeout=stage.timeout_sec)
            except asyncio.TimeoutError:
                raise PipelineError(f"Stage {stage.name} timed out after {stage.timeout_sec}s")

            for key in stage.outputs:
                run_context[key] = result.get(key)

        return self._format_output(pipeline.output_type, run_context)

    def _format_output(self, output_type: str, context: dict) -> dict:
        """Produce the standardized output format for this pipeline type."""
        formatter = FORMATTERS[output_type]
        return formatter(context)
```

### Pipeline 1: Audio → Transcript

```python
pipeline_audio_transcript = Pipeline(
    name="audio_transcript",
    stages=[
        Stage("vad_segment", vad_segment, inputs=["audio_path"], outputs=["segments"], timeout_sec=30),
        Stage("whisper_transcribe", whisper_transcribe, inputs=["audio_path", "segments"], outputs=["transcript"], npu_required=True, timeout_sec=120),
        Stage("format_output", format_transcript, inputs=["transcript", "source_path", "duration_sec"], outputs=[], timeout_sec=5),
    ],
    output_type="transcript"
)
```

**vad_segment function** — takes `audio_path`, runs VAD, returns speech segments with timestamps. Uses the same VAD gate from Phase 2.

**whisper_transcribe function** — takes the audio file plus the VAD segments (it needs the audio itself, not just timestamps), calls `phone.npu.transcribe` via the inference queue (priority 2 — batch). Returns full transcript text.

**format_transcript function** — produces:
```json
{
  "pipeline": "audio_transcript",
  "source": "~/ingest/audio/20260714_150322_raw_a3f2c.wav",
  "duration_sec": 14.2,
  "segments": [
    {"speaker": null, "start": 0.0, "end": 3.2, "text": "Reminder to check the flake update"}
  ],
  "full_text": "Reminder to check the flake update.",
  "word_count": 6,
  "processing_time_ms": 4800
}
```

### Pipeline 2: Image → OCR

```python
pipeline_image_ocr = Pipeline(
    name="image_ocr",
    stages=[
        Stage("orient_correct", orient_correct, inputs=["image_path"], outputs=["corrected_path"], timeout_sec=10),
        Stage("ocr_run", ocr_run, inputs=["corrected_path"], outputs=["blocks"], npu_required=True, timeout_sec=60),
        Stage("order_blocks", order_blocks, inputs=["blocks"], outputs=["ordered_blocks"], timeout_sec=5),
        Stage("format_output", format_ocr, inputs=["ordered_blocks", "source_path"], outputs=[], timeout_sec=5),
    ],
    output_type="ocr"
)
```

**orient_correct function** — reads EXIF orientation, rotates image, deskews if skew > 2 degrees.

**ocr_run function** — calls `phone.npu.ocr` via the inference queue. Returns text blocks with bounding boxes.

**order_blocks function** — sorts blocks top-to-bottom, left-to-right (reading order). Merges adjacent blocks on the same line.

**format_ocr function** — produces:
```json
{
  "pipeline": "image_ocr",
  "source": "~/ingest/images/20260714_150322_frame_a3f2c.jpg",
  "resolution": [1920, 1080],
  "blocks": [
    {"text": "Meeting Notes", "bbox": [50,20,400,60], "confidence": 0.98},
    {"text": "Action items:\n1. Update flake lock", "bbox": [50,80,600,200], "confidence": 0.95}
  ],
  "full_text": "Meeting Notes\nAction items:\n1. Update flake lock",
  "word_count": 9,
  "processing_time_ms": 1200
}
```

### Pipeline 3: Share → Extract → Summarize

```python
pipeline_share_extract = Pipeline(
    name="share_extract",
    stages=[
        Stage("classify_intent", classify_intent, inputs=["raw_share"], outputs=["intent"], npu_required=True, timeout_sec=10),
        Stage("extract_content", extract_content, inputs=["raw_share", "intent"], outputs=["extracted_text", "title"], timeout_sec=30),
        Stage("summarize_if_long", summarize_if_long, inputs=["extracted_text"], outputs=["summary", "summarized"], npu_required=True, timeout_sec=60),
        Stage("embed_content", embed_content, inputs=["extracted_text"], outputs=["embedding"], npu_required=True, timeout_sec=10),
        Stage("format_output", format_share, inputs=["intent", "extracted_text", "title", "summary", "summarized", "raw_share", "embedding"], outputs=[], timeout_sec=5),
    ],
    output_type="summary"
)
```

**classify_intent function** — calls `phone.npu.classify` with labels: `["store", "query", "command", "ignore"]`.

**extract_content function** — if URL: uses readability-lxml or similar to extract main article text + title. If plain text: use as-is. If image: route to pipeline 2.

**summarize_if_long function** — **only if `extracted_text` > 500 words**: calls `phone.npu.llm_infer` with a summarization prompt and returns `summary`, `summarized: true`. Shorter content returns `summary: null`, `summarized: false`. (Matches the design doc; the summarize stage is also skipped with `summarized: false` when the inference queue is saturated — see Guardrails.)

**embed_content function** — calls `phone.npu.embed` with extracted text.

**format_share function** — produces:
```json
{
  "pipeline": "share_extract",
  "source": "https://example.com/article",
  "content_type": "article",
  "title": "How Nix Flakes Work",
  "extracted_text": "Nix flakes provide...",
  "word_count": 1200,
  "summarized": true,
  "summary": "A guide to Nix flakes covering inputs, outputs, and lock files...",
  "embedding": [0.0123],
  "tags": ["nix", "flakes"],
  "processing_time_ms": 4500
}
```

### ingest/capture_trigger.py — Automatic Pipeline Trigger

When a capture tool writes a file, it fires an event. This module listens for those events and starts the appropriate pipeline.

```python
class CaptureTrigger:
    def __init__(self, executor: PipelineExecutor):
        self.executor = executor
        # Maps capture type → pipeline name
        self.routes = {
            "audio": "audio_transcript",
            "image": "image_ocr",
            "screenshot": "image_ocr",   # Same OCR pipeline
            "share": "share_extract",
        }

    def on_capture(self, capture_type: str, capture_result: dict):
        """Called by capture tools after successful capture. Fire-and-forget."""
        pipeline_name = self.routes.get(capture_type)
        if not pipeline_name:
            return

        context = {
            "audio_path": capture_result.get("audio_path"),
            "image_path": capture_result.get("image_path"),
            "raw_share": capture_result,
            "duration_sec": capture_result.get("duration_sec"),
            "source_path": capture_result.get("audio_path") or capture_result.get("image_path"),
        }

        # Truly non-blocking: schedule, don't await. The capture tool
        # returns immediately; the pipeline writes to processed/ when done.
        asyncio.create_task(self._run_and_store(pipeline_name, context))

    async def _run_and_store(self, pipeline_name: str, context: dict):
        try:
            result = await self.executor.run(pipeline_name, context)
            write_processed(result)
        except Exception as e:
            log_pipeline_error(pipeline_name, context, e)   # → ~/ingest/errors/
```

### tools/pipeline_trigger.py — Manual Pipeline Tool

A tool to manually trigger a pipeline on existing files:

```json
{
  "tool": "phone.pipeline.run",
  "input": {
    "pipeline": "audio_transcript",
    "files": { "audio_path": "~/ingest/audio/some_existing_file.wav" }
  },
  "output": {
    "pipeline_id": "a3f2c8",
    "status": "running"
  }
}
```

---

## Test Procedure

1. Test audio → transcript:
   - Record audio via capture_audio
   - Verify auto-trigger runs pipeline
   - Check `~/ingest/processed/transcripts/` for JSON output
   - Verify transcript text is reasonable

2. Test image → OCR:
   - Capture a photo of a document
   - Verify OCR extracts text
   - Check block ordering is correct

3. Test share → extract:
   - Share a URL to Termux
   - Verify extraction + summarization (use an article > 500 words)
   - Check embedding is 384-dim

4. Test manual pipeline trigger:
   - Call `phone.pipeline.run` with existing audio file
   - Verify pipeline completes and writes output

---

## Acceptance Criteria

- [ ] Audio capture auto-triggers → transcript appears in `processed/transcripts/`
- [ ] Image capture auto-triggers → OCR output in `processed/ocr/`
- [ ] Share capture auto-triggers → summary + embedding in `processed/summaries/`
- [ ] Content ≤ 500 words gets `summarized: false, summary: null`; > 500 words gets a real summary
- [ ] Manual pipeline trigger works via `phone.pipeline.run`
- [ ] Output JSON files follow correct schema for each pipeline type
- [ ] Error handling: pipeline stage failure logs to `~/ingest/errors/` and returns error for that stage
- [ ] Pipeline timeout kills long-running stages and returns partial results
- [ ] Multiple pipelines can run concurrently (CPU stages parallel, inference stages serialized by queue)

---

## Guardrails

- **Inference stages are serialized by the priority queue.** Multiple pipelines can be in-flight, but inference stages from different pipelines queue up.
- **Pipeline errors don't corrupt the source file.** Source files in `audio/`, `images/`, etc. are read-only. Pipeline writes to `processed/`.
- **No automatic retry on pipeline failure.** If a stage fails, the pipeline records the error and stops. User can manually re-run via `phone.pipeline.run`.
- **Summarization is optional.** If the inference queue is saturated, the summarize stage is skipped (marked `"summarized": false`). The extracted text and embedding are still produced.

---

## Git Commit

```bash
git add -A
git commit -m "feat(phone-mcp): processing pipelines — audio, OCR, share extract"
git tag phone-mcp-phase-3
git push origin phone
```

Rollback: `git revert HEAD`. Pipelines revert. Individual capture + compute tools still work independently.
