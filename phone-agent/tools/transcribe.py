from npu import get_queue
from npu.bridge import InferenceError
from npu.queue import PRIORITY_SCHEDULED

MODEL = "whisper-small.en-q8_0"


def register(mcp):
    @mcp.tool(name="phone.npu.transcribe")
    async def transcribe(audio_path: str, language: str = "en",
                         temperature: float = 0.0) -> dict:
        """Transcribe an audio file already on the phone filesystem with
        whisper-small.en (CPU). Input: absolute audio_path (wav), optional
        language and sampling temperature. Returns timestamped segments,
        full_text, processing_time_ms, and model_used. Errors:
        AUDIO_TOO_LONG, MODEL_NOT_LOADED, NPU_BUSY."""
        try:
            return await get_queue().submit(
                MODEL,
                {"audio_path": audio_path, "language": language,
                 "temperature": temperature},
                priority=PRIORITY_SCHEDULED)
        except InferenceError as e:
            return {"error": e.code, "message": e.message}
