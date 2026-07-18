"""Pipeline output formatters and processed-artifact writer (Phase 3).

Formatters take the full run context and return the fixed output schema
for their pipeline; every field is guarded against missing context.
"""

import json
from pathlib import Path
from typing import Callable

from ingest.store import generate_filename


def format_transcript(ctx: dict) -> dict:
    transcript = ctx.get("transcript") or {}
    full_text = transcript.get("full_text") or ""
    duration = ctx.get("duration_sec")
    return {
        "pipeline": "audio_transcript",
        "source": ctx.get("source_path"),
        "duration_sec": float(duration) if duration is not None else None,
        "segments": [{"speaker": None,
                      "start": float(s.get("start_sec", 0.0)),
                      "end": float(s.get("end_sec", 0.0)),
                      "text": s.get("text") or ""}
                     for s in transcript.get("segments") or []],
        "full_text": full_text,
        "word_count": len(full_text.split()),
        "processing_time_ms": int(ctx.get("processing_time_ms") or 0),
    }


def format_ocr(ctx: dict) -> dict:
    blocks = ctx.get("ordered_blocks") or []
    full_text = "\n".join(b.get("text") or "" for b in blocks)
    return {
        "pipeline": "image_ocr",
        "source": ctx.get("source_path"),
        "resolution": ctx.get("resolution"),
        "blocks": blocks,
        "full_text": full_text,
        "word_count": len(full_text.split()),
        "processing_time_ms": int(ctx.get("processing_time_ms") or 0),
    }


def format_share(ctx: dict) -> dict:
    text = ctx.get("extracted_text") or ""
    intent = ctx.get("intent")
    if isinstance(intent, dict):
        intent = intent.get("label")
    return {
        "pipeline": "share_extract",
        "source": ctx.get("source"),
        "content_type": ctx.get("content_type"),
        "title": ctx.get("title"),
        "extracted_text": text,
        "word_count": len(text.split()),
        "summarized": bool(ctx.get("summarized")),
        "summary": ctx.get("summary"),
        "embedding": list(ctx.get("embedding") or []),
        "tags": [],
        "intent": intent,
        "processing_time_ms": int(ctx.get("processing_time_ms") or 0),
    }


FORMATTERS: dict[str, Callable[[dict], dict]] = {
    "transcript": format_transcript,
    "ocr": format_ocr,
    "summary": format_share,
}

_DESTS = {
    "audio_transcript": ("processed/transcripts", "transcript"),
    "image_ocr": ("processed/ocr", "ocr"),
    "share_extract": ("processed/summaries", "summary"),
}


def write_processed(result: dict) -> Path:
    subdir, kind = _DESTS[result["pipeline"]]
    path = generate_filename(subdir, kind, "json")
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return path
