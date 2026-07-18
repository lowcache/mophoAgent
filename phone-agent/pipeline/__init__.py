"""Pipeline executor singleton (lazy, same pattern as npu/__init__)."""

_executor = None


def get_executor():
    global _executor
    if _executor is None:
        from pipeline.executor import PipelineExecutor
        from pipeline import audio_transcript, image_ocr, share_extract
        _executor = PipelineExecutor()
        _executor.register(audio_transcript.PIPELINE)
        _executor.register(image_ocr.PIPELINE)
        _executor.register(share_extract.PIPELINE)
    return _executor
