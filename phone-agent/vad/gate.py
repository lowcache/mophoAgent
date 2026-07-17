"""Silero VAD over a whole clip (record-then-trim baseline, Phase 2).

Raw onnxruntime — the silero-vad pip package is not installable on
bionic. Handles both model generations by inspecting the graph inputs:
v5 (single `state` [2,1,128], 64-sample context prepended per 16 kHz
chunk) and v4 (`h`/`c` [2,1,64], no context). CPU-only, in-process
singleton session — same pattern as npu/ocr_engine.py.
"""

import threading

import numpy as np

from config.settings import VAD_MODEL_PATH

# Span post-processing defaults from snakers4/silero-vad
# get_speech_timestamps; neg-threshold hysteresis is threshold - 0.15.
MIN_SPEECH_MS = 250
SPEECH_PAD_MS = 30
# mode -> min silence (ms) that closes a span; higher mode trims harder.
MODE_MIN_SILENCE_MS = {0: 300, 1: 200, 2: 150, 3: 100}

_lock = threading.Lock()
_session = None


def _load():
    global _session
    with _lock:
        if _session is None:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            _session = ort.InferenceSession(
                str(VAD_MODEL_PATH), sess_options=opts,
                providers=["CPUExecutionProvider"])
        return _session


class VADGate:
    def __init__(self, threshold: float = 0.5, mode: int = 3):
        self.threshold = threshold
        self.min_silence_ms = MODE_MIN_SILENCE_MS.get(int(mode), 100)

    def speech_spans(self, audio: np.ndarray, sample_rate: int) -> list[tuple[float, float]]:
        """[(start_sec, end_sec), ...] speech segments over the clip,
        padded by SPEECH_PAD_MS and merged."""
        if sample_rate not in (8000, 16000):
            raise ValueError(f"Silero VAD supports 8/16 kHz, got {sample_rate}")
        sess = _load()
        names = {i.name for i in sess.get_inputs()}
        window = 512 if sample_rate == 16000 else 256
        context_size = 64 if sample_rate == 16000 else 32
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        sr = np.array(sample_rate, dtype=np.int64)

        v5 = "state" in names
        state = np.zeros((2, 1, 128), dtype=np.float32)
        h = np.zeros((2, 1, 64), dtype=np.float32)
        c = np.zeros((2, 1, 64), dtype=np.float32)
        context = np.zeros(context_size, dtype=np.float32)

        probs = []
        for off in range(0, len(audio), window):
            chunk = audio[off:off + window]
            if len(chunk) < window:
                chunk = np.pad(chunk, (0, window - len(chunk)))
            if v5:
                inp = np.concatenate([context, chunk])[None, :]
                out, state = sess.run(None, {"input": inp, "state": state, "sr": sr})
                context = chunk[-context_size:]
            else:
                out, h, c = sess.run(None, {"input": chunk[None, :], "sr": sr, "h": h, "c": c})
            probs.append(float(out.reshape(-1)[0]))

        return self._spans(probs, window / sample_rate, len(audio) / sample_rate)

    def _spans(self, probs: list[float], step: float, total: float) -> list[tuple[float, float]]:
        neg_threshold = max(self.threshold - 0.15, 0.01)
        min_silence = self.min_silence_ms / 1000.0
        min_speech = MIN_SPEECH_MS / 1000.0
        pad = SPEECH_PAD_MS / 1000.0

        raw = []
        start = end = None
        for i, p in enumerate(probs):
            t0, t1 = i * step, (i + 1) * step
            if p >= self.threshold:
                if start is None:
                    start = t0
                end = t1
            elif start is not None and p < neg_threshold and t0 - end >= min_silence:
                raw.append((start, end))
                start = end = None
        if start is not None:
            raw.append((start, end))

        spans = []
        for s, e in raw:
            if e - s < min_speech:
                continue
            s, e = max(0.0, s - pad), min(total, e + pad)
            if spans and s <= spans[-1][1]:
                spans[-1] = (spans[-1][0], max(spans[-1][1], e))
            else:
                spans.append((s, e))
        return spans
