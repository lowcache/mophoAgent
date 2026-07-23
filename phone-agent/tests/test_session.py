"""The voice cycle must surface the TTS outcome and never lose the answer
when TTS fails. Run: python tests/test_session.py"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.session import VoiceSession, IDLE


class StubRouter:
    async def route(self, text: str):
        return f"answer:{text}", "local"


class OkTTS:
    async def speak(self, text: str) -> dict:
        return {"spoken": True, "chars": len(text), "truncated": False,
                "elapsed_ms": 2400}


class ErrTTS:
    async def speak(self, text: str) -> dict:
        return {"spoken": False, "error": "TTS_UNAVAILABLE",
                "message": "termux-tts-speak not found"}


class RaisingTTS:
    async def speak(self, text: str) -> dict:
        raise RuntimeError("engine exploded")


class HangingTTS:
    async def speak(self, text: str) -> dict:
        await asyncio.sleep(10)
        return {"spoken": True}


def _ask(tts, timeout=30.0):
    s = VoiceSession(StubRouter(), tts, state_timeout_sec=timeout)
    out = asyncio.run(s.ask(text="hi"))
    assert s.state == IDLE
    return out


def test_success_surfaces_spoken():
    out = _ask(OkTTS())
    assert out["response"] == "answer:hi" and out["source"] == "local"
    assert out["spoken"]["spoken"] is True
    assert out["spoken"]["elapsed_ms"] == 2400


def test_tts_error_surfaces_and_keeps_response():
    out = _ask(ErrTTS())
    assert out["response"] == "answer:hi"          # answer is not lost
    assert out["spoken"]["spoken"] is False
    assert out["spoken"]["error"] == "TTS_UNAVAILABLE"


def test_raising_tts_does_not_fail_the_cycle():
    out = _ask(RaisingTTS())
    assert out["response"] == "answer:hi"
    assert out["spoken"]["error"] == "TTS_FAILED"
    assert "exploded" in out["spoken"]["message"]


def test_hanging_tts_times_out_but_returns_answer():
    out = _ask(HangingTTS(), timeout=0.1)
    assert out["response"] == "answer:hi"
    assert out["spoken"]["error"] == "TTS_TIMEOUT"


if __name__ == "__main__":
    tests = [test_success_surfaces_spoken,
             test_tts_error_surfaces_and_keeps_response,
             test_raising_tts_does_not_fail_the_cycle,
             test_hanging_tts_times_out_but_returns_answer]
    for t in tests:
        t()
    print(f"{len(tests)}/{len(tests)} PASS")
