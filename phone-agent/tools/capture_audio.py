import asyncio
import json
import math
import time
import wave

import numpy as np

from config.settings import INGEST_DIR
from ingest.store import generate_filename
from tools.capture_common import CaptureError, run_cli, raise_for_termux_api
from vad.gate import VADGate


# stdlib wave instead of soundfile: pip/uv soundfile wheels bundle glibc
# libsndfile that fails bionic dlopen, and ffmpeg already guarantees
# 16-bit mono PCM here.
def _read_wav(path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2 or w.getnchannels() != 1:
            raise CaptureError("DECODE_FAILED", "expected 16-bit mono WAV from ffmpeg")
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0, sr


def _write_wav(path, audio: np.ndarray, sr: int):
    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def register(mcp):
    @mcp.tool(name="phone.capture.audio")
    async def capture_audio(max_duration_sec: int = 30, sample_rate: int = 16000,
                            vad_threshold: float = 0.5, vad_mode: int = 3) -> dict:
        """Record from the microphone (termux-microphone-record,
        record-then-trim: no live mic stream in Termux), VAD-trim
        leading/trailing silence with Silero VAD, store the trimmed
        16-bit mono WAV under ~/ingest/audio/. Returns audio_path,
        duration_sec, peak_level_db, vad_triggered. Errors:
        MICROPHONE_BUSY, VAD_TIMEOUT (no speech; recording deleted),
        PERMISSION_DENIED, DECODE_FAILED."""
        if sample_rate not in (8000, 16000):
            return {"error": "INVALID_SAMPLE_RATE",
                    "message": "Silero VAD supports 8000 or 16000 Hz"}
        tmp = INGEST_DIR / "audio" / f".rec_{time.time_ns()}.m4a"
        wav_tmp = tmp.with_suffix(".wav")
        try:
            rec = await run_cli(["termux-microphone-record", "-f", str(tmp),
                                 "-l", str(max_duration_sec),
                                 "-r", str(sample_rate), "-c", "1"])
            raise_for_termux_api(rec, "MICROPHONE")

            # The CLI returns immediately; recording runs in the API app
            # until the -l limit. Poll until it stops, then flush.
            deadline = time.monotonic() + max_duration_sec + 5
            while time.monotonic() < deadline:
                info = await run_cli(["termux-microphone-record", "-i"])
                try:
                    if not json.loads(info.stdout).get("isRecording", False):
                        break
                except json.JSONDecodeError:
                    break
                await asyncio.sleep(0.5)
            await run_cli(["termux-microphone-record", "-q"])

            if not tmp.exists() or tmp.stat().st_size == 0:
                raise CaptureError("CAPTURE_FAILED", "recording produced no file")

            # MediaRecorder cannot emit WAV; transcode (pkg install ffmpeg).
            ff = await run_cli(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp),
                                "-ac", "1", "-ar", str(sample_rate), str(wav_tmp)],
                               timeout=60)
            if ff.returncode != 0:
                raise CaptureError("DECODE_FAILED", ff.stderr.strip()[:200])

            audio, sr = await asyncio.to_thread(_read_wav, wav_tmp)
            gate = VADGate(threshold=vad_threshold, mode=vad_mode)
            spans = await asyncio.to_thread(gate.speech_spans, audio, sr)
            if not spans:
                return {"error": "VAD_TIMEOUT",
                        "message": "no speech detected; recording deleted"}

            trimmed = audio[int(spans[0][0] * sr):int(spans[-1][1] * sr)]
            out_path = generate_filename("audio", "raw", "wav")
            await asyncio.to_thread(_write_wav, out_path, trimmed, sr)
            peak = float(np.max(np.abs(trimmed))) if len(trimmed) else 0.0
            return {"audio_path": str(out_path),
                    "duration_sec": round(len(trimmed) / sr, 1),
                    "peak_level_db": round(20 * math.log10(peak), 1) if peak > 0 else -120.0,
                    "vad_triggered": True}
        except CaptureError as e:
            return {"error": e.code, "message": e.message}
        finally:
            tmp.unlink(missing_ok=True)
            wav_tmp.unlink(missing_ok=True)
