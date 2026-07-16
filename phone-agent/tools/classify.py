from npu import get_queue
from npu.bridge import InferenceError
from npu.queue import PRIORITY_INTERACTIVE

MODEL = "qwen2.5-1.5b-q4-classify"
DEFAULT_LABELS = ["store", "query", "command", "ignore"]


def register(mcp):
    @mcp.tool(name="phone.npu.classify")
    async def classify(text: str, labels: list[str] | None = None) -> dict:
        """Classify text into one of the given labels (default: store,
        query, command, ignore) using qwen2.5-1.5b with grammar-constrained
        output. Interactive priority — preempts batch work; blocks routing
        decisions. Returns label, confidence, per-label scores,
        processing_time_ms. Errors: MODEL_NOT_LOADED, NPU_BUSY."""
        try:
            return await get_queue().submit(
                MODEL, {"text": text, "labels": labels or DEFAULT_LABELS},
                priority=PRIORITY_INTERACTIVE)
        except InferenceError as e:
            return {"error": e.code, "message": e.message}
