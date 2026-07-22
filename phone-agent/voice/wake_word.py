"""Experimental wake-word detector (build-last per the Phase 6 charter).

Continuous mic streaming is the least reliable piece of the Termux stack and
the mic is contended with phone.capture.audio, so no detector is wired by
default. This is a typed stub: constructing or using it raises, so the voice
session reports WAKE_WORD_UNAVAILABLE rather than silently pretending to listen.
A real implementation would load an OpenWakeWord ONNX model and stream 30ms
frames; that needs an operator-placed model file (deferred, non-blocking).
"""


class WakeWordUnavailable(RuntimeError):
    pass


class WakeWordDetector:
    def __init__(self, model_path: str | None = None, sensitivity: float = 0.5):
        raise WakeWordUnavailable(
            "wake-word detection is not implemented; install an OpenWakeWord "
            "model and wire a streaming mic source to enable it")

    def listen(self, callback) -> None:
        raise WakeWordUnavailable("wake-word detection is not implemented")
