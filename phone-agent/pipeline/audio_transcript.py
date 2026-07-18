"""Audio transcript pipeline: VAD spans then whisper (Phase 3).

capture.audio guarantees 16-bit mono PCM 16 kHz WAV, but the header is
read and enforced (Silero VAD accepts 8/16 kHz only). An empty span list
still goes to whisper — the capture layer already VAD-gated the clip.
"""

import wave

import numpy as np

from npu.queue import PRIORITY_BATCH
from pipeline.executor import Pipeline, Stage, StageFailed
from vad.gate import VADGate


def _vad_segment(audio_path: str) -> dict:
    with wave.open(audio_path, "rb") as w:
        rate = w.getframerate()
        width = w.getsampwidth()
        channels = w.getnchannels()
        frames = w.readframes(w.getnframes())
    if rate not in (8000, 16000):
        raise StageFailed("UNSUPPORTED_RATE",
                          f"Silero VAD supports 8/16 kHz, got {rate}")
    if width != 2:
        raise StageFailed("UNSUPPORTED_FORMAT",
                          f"expected 16-bit PCM, got {width * 8}-bit")
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    spans = VADGate().speech_spans(audio, rate)
    return {"segments": [{"start": float(s), "end": float(e)}
                         for s, e in spans]}


async def _whisper_transcribe(audio_path: str, segments: list) -> dict:
    from npu import get_queue
    from npu.bridge import InferenceError
    try:
        result = await get_queue().submit(
            "whisper-small.en-q8_0",
            {"audio_path": audio_path, "language": "en", "temperature": 0.0},
            priority=PRIORITY_BATCH)
    except InferenceError as e:
        raise StageFailed(e.code, e.message) from e
    if isinstance(result, dict) and "error" in result:
        raise StageFailed(str(result["error"]),
                          str(result.get("message", "inference failed")))
    return {"transcript": result}


PIPELINE = Pipeline(
    name="audio_transcript",
    output_type="transcript",
    stages=[
        Stage(name="vad_segment", fn=_vad_segment,
              inputs=["audio_path"], outputs=["segments"], timeout_sec=30),
        Stage(name="whisper_transcribe", fn=_whisper_transcribe,
              inputs=["audio_path", "segments"], outputs=["transcript"],
              npu_required=True, timeout_sec=120),
    ],
)
