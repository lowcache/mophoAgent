from npu import get_queue
from npu.bridge import InferenceError
from npu.queue import PRIORITY_INTERACTIVE

MODEL = "qwen2.5-1.5b-q4"


def register(mcp):
    @mcp.tool(name="phone.npu.llm_infer")
    async def llm_infer(prompt: str, max_tokens: int = 256,
                        temperature: float = 0.7) -> dict:
        """Fast-path local LLM completion on qwen2.5-1.5b (CPU llama-server,
        1024-token context). Interactive priority — preempts batch work.
        Returns response text, tokens_generated, ttft_ms, tokens_per_sec,
        model_used, routed_to_laptop=false. Errors: MODEL_NOT_LOADED,
        NPU_BUSY."""
        try:
            return await get_queue().submit(
                MODEL,
                {"prompt": prompt, "max_tokens": max_tokens,
                 "temperature": temperature},
                priority=PRIORITY_INTERACTIVE)
        except InferenceError as e:
            return {"error": e.code, "message": e.message}
