from npu import get_queue
from npu.bridge import InferenceError
from npu.queue import PRIORITY_SCHEDULED

MODEL = "ocr-model"


def register(mcp):
    @mcp.tool(name="phone.npu.ocr")
    async def ocr(image_path: str, languages: list[str] | None = None) -> dict:
        """Extract printed text from an image on the phone filesystem
        (ONNX OCR, CPU). Input: absolute image_path, optional language
        list (default ["en"]). Returns text blocks with bounding boxes and
        confidence, reading-order full_text, and processing_time_ms.
        Errors: MODEL_NOT_LOADED, NPU_BUSY."""
        try:
            return await get_queue().submit(
                MODEL,
                {"image_path": image_path, "languages": languages or ["en"]},
                priority=PRIORITY_SCHEDULED)
        except InferenceError as e:
            return {"error": e.code, "message": e.message}
