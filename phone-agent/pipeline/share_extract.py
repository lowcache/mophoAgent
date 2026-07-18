"""Share → classify → extract → summarize → embed (Phase 3, Pipeline 3).

Image/file shares are routed to the image_ocr pipeline by the capture
trigger before this pipeline is chosen; here only url/text/plain-file
shares arrive. Summarization is bounded by the qwen 1024-token context:
input is head-truncated to SUMMARY_INPUT_CHARS (deviation flagged in the
phase-3 relay) and skipped entirely when the inference queue is
saturated, per the phase guardrails.
"""

from pathlib import Path

import httpx

from npu import get_queue
from npu.queue import PRIORITY_BATCH
from pipeline.executor import Pipeline, Stage, StageFailed
from pipeline.extract_html import extract_main_content

CLASSIFY_LABELS = ["store", "query", "command", "ignore"]
SUMMARY_MIN_WORDS = 500
SUMMARY_INPUT_CHARS = 2500   # ~600 tokens; qwen serves a 1024-token context
EMBED_INPUT_CHARS = 800      # embed backend caps input at 256 tokens
QUEUE_SATURATED_DEPTH = 3
FETCH_TIMEOUT = 20.0
TEXT_FILE_EXTS = {".txt", ".md", ".text", ".log", ".csv", ".json"}
UA = "Mozilla/5.0 (Android 16; Mobile) phone-agent/0.1"


async def _submit(model: str, payload: dict):
    """Queue submit with both NPU failure shapes mapped to StageFailed
    (bridge raises InferenceError; tool layer wraps into error dicts)."""
    from npu.bridge import InferenceError
    try:
        result = await get_queue().submit(model, payload,
                                          priority=PRIORITY_BATCH)
    except InferenceError as e:
        raise StageFailed(e.code, e.message) from e
    if isinstance(result, dict) and "error" in result:
        raise StageFailed(str(result["error"]),
                          str(result.get("message", "inference failed")))
    return result


async def classify_intent(raw_share: dict) -> dict:
    text = str(raw_share.get("content", ""))[:500]
    result = await _submit("qwen2.5-1.5b-q4-classify",
                           {"text": text, "labels": CLASSIFY_LABELS})
    return {"intent": result["label"]}


async def extract_content(raw_share: dict, intent: str) -> dict:
    kind = raw_share.get("type")
    content = str(raw_share.get("content", ""))

    if kind == "url":
        async with httpx.AsyncClient(follow_redirects=True,
                                     timeout=FETCH_TIMEOUT,
                                     headers={"User-Agent": UA}) as client:
            try:
                resp = await client.get(content)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                raise StageFailed("FETCH_FAILED", f"{content}: {e}")
        ctype = resp.headers.get("content-type", "")
        if "html" in ctype:
            extracted = extract_main_content(resp.text)
            return {"extracted_text": extracted["text"],
                    "title": extracted["title"],
                    "content_type": "article", "source": content}
        if ctype.startswith("text/"):
            return {"extracted_text": resp.text, "title": None,
                    "content_type": "text", "source": content}
        raise StageFailed("UNSUPPORTED_CONTENT",
                          f"cannot extract {ctype or 'unknown'} at {content}")

    if kind == "text":
        return {"extracted_text": content, "title": None,
                "content_type": "text", "source": "share:text"}

    if kind == "file" and Path(content).suffix.lower() in TEXT_FILE_EXTS:
        try:
            text = Path(content).read_text(errors="replace")
        except OSError as e:
            raise StageFailed("FETCH_FAILED", f"{content}: {e}")
        return {"extracted_text": text, "title": Path(content).name,
                "content_type": "text", "source": content}

    raise StageFailed("SHARE_NOT_SUPPORTED",
                      f"no extractor for share type {kind!r}")


async def summarize_if_long(extracted_text: str) -> dict:
    text = extracted_text or ""
    if len(text.split()) <= SUMMARY_MIN_WORDS:
        return {"summary": None, "summarized": False}
    if get_queue().depth >= QUEUE_SATURATED_DEPTH:
        return {"summary": None, "summarized": False}
    prompt = ("Summarize the following content in 3-4 plain sentences. "
              "Output only the summary.\n\n" + text[:SUMMARY_INPUT_CHARS])
    result = await _submit(
        "qwen2.5-1.5b-q4",
        {"prompt": prompt, "max_tokens": 160, "temperature": 0.3})
    return {"summary": result["response"].strip(), "summarized": True}


async def embed_content(extracted_text: str) -> dict:
    text = (extracted_text or "")[:EMBED_INPUT_CHARS]
    if not text.strip():
        return {"embedding": None}
    result = await _submit("all-minilm-l6-v2-q4",
                           {"text": text, "normalize": True})
    return {"embedding": result["embedding"]}


PIPELINE = Pipeline(
    name="share_extract",
    output_type="summary",
    stages=[
        Stage("classify_intent", classify_intent,
              inputs=["raw_share"], outputs=["intent"],
              npu_required=True, timeout_sec=30),
        Stage("extract_content", extract_content,
              inputs=["raw_share", "intent"],
              outputs=["extracted_text", "title", "content_type", "source"],
              timeout_sec=30),
        Stage("summarize_if_long", summarize_if_long,
              inputs=["extracted_text"], outputs=["summary", "summarized"],
              npu_required=True, timeout_sec=120),
        Stage("embed_content", embed_content,
              inputs=["extracted_text"], outputs=["embedding"],
              npu_required=True, timeout_sec=30),
    ],
)
