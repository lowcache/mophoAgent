"""Auto-start a processing pipeline when a capture succeeds (Phase 3).

Capture tools call get_trigger().on_capture(...) after a successful
capture; the pipeline runs as a fire-and-forget task and writes its
output to ingest/processed/ (or an error record to ingest/errors/).
Stage timeouts include time spent waiting in the serialized inference
queue.
"""

import asyncio
import json
import time
from pathlib import Path

from ingest.store import generate_filename

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"}

_ROUTES = {
    "audio": "audio_transcript",
    "image": "image_ocr",
    "screenshot": "image_ocr",
    "share": "share_extract",
}

_trigger = None


def get_trigger():
    global _trigger
    if _trigger is None:
        from pipeline import get_executor
        _trigger = CaptureTrigger(get_executor())
    return _trigger


def _json_safe(value):
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return f"<list len={len(value)}>" if len(value) > 20 \
            else [_json_safe(v) for v in value]
    if isinstance(value, str) and len(value) > 500:
        return value[:500] + "…"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return repr(value)[:200]


def log_pipeline_error(pipeline: str, stage: str, code: str, message: str,
                       context: dict) -> Path:
    record = {
        "pipeline": pipeline,
        "stage": stage,
        "error": code,
        "message": message,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "partial_context": _json_safe(context),
    }
    path = generate_filename("errors", "pipeline", "json")
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    return path


class CaptureTrigger:
    def __init__(self, executor):
        self.executor = executor
        self.tasks: set[asyncio.Task] = set()

    def on_capture(self, capture_type: str, capture_result: dict):
        """Fire-and-forget; never raises into the capture tool."""
        if not isinstance(capture_result, dict) or "error" in capture_result:
            return
        pipeline_name = _ROUTES.get(capture_type)
        if pipeline_name is None:
            return

        # Image shares carry a file path — they belong to the OCR
        # pipeline, not text extraction.
        if capture_type == "share":
            content = str(capture_result.get("content", ""))
            if (capture_result.get("type") in ("image", "file")
                    and Path(content).suffix.lower() in IMAGE_EXTS):
                pipeline_name = "image_ocr"
                context = {"image_path": content, "source_path": content}
            else:
                context = {"raw_share": capture_result, "source_path": None}
        else:
            source = (capture_result.get("audio_path")
                      or capture_result.get("image_path"))
            context = {
                "audio_path": capture_result.get("audio_path"),
                "image_path": capture_result.get("image_path"),
                "duration_sec": capture_result.get("duration_sec"),
                "source_path": source,
            }

        task = asyncio.get_running_loop().create_task(
            self._run_and_store(pipeline_name, context))
        # Keep a strong reference so the task is not garbage-collected.
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _run_and_store(self, pipeline_name: str, context: dict):
        from pipeline.executor import PipelineError
        from pipeline.format import write_processed
        try:
            result = await self.executor.run(pipeline_name, context)
            write_processed(result)
        except PipelineError as e:
            log_pipeline_error(e.pipeline, e.stage, e.code, e.message,
                               e.partial)
        except Exception as e:
            log_pipeline_error(pipeline_name, "?", "UNEXPECTED",
                               f"{type(e).__name__}: {e}", context)
