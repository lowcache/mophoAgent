from npu import get_queue
from npu.bridge import InferenceError
from npu.queue import PRIORITY_BATCH

MODEL = "all-minilm-l6-v2-q4"


def register(mcp):
    @mcp.tool(name="phone.npu.embed")
    async def embed(text: str, normalize: bool = True) -> dict:
        """Embed text with all-MiniLM-L6-v2 (384 dims, CPU llama-server).
        Input: text (<=256 tokens), normalize flag for unit length.
        Returns embedding vector, dimensions, processing_time_ms. Batch
        priority — queued behind interactive work. Errors:
        MODEL_NOT_LOADED, NPU_BUSY."""
        try:
            return await get_queue().submit(
                MODEL, {"text": text, "normalize": normalize},
                priority=PRIORITY_BATCH)
        except InferenceError as e:
            return {"error": e.code, "message": e.message}
