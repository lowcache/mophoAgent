"""Local text-to-speech via Android's system TTS engine (termux-tts-speak).

No cloud TTS (charter guardrail): termux-tts-speak drives the on-device engine
(Google/Samsung). Text is fed on stdin, never as an argv, so long responses and
shell-special characters need no quoting. Volume is left to the phone's media
stream — we never force it up.
"""

import asyncio
import subprocess


class TTSEngine:
    def __init__(self, rate: float = 1.0, pitch: float = 1.0, stream: str = "MUSIC"):
        # stream MUSIC ties playback to the media volume the user already set.
        self.rate = rate
        self.pitch = pitch
        self.stream = stream

    async def speak(self, text: str, timeout_sec: float = 60.0) -> dict:
        """Speak `text` through the system TTS engine and block until playback
        finishes (termux-tts-speak returns when the utterance completes).
        Returns {"spoken": True, "chars": <n>}. Errors: TTS_EMPTY,
        TTS_UNAVAILABLE (termux-tts-speak not installed), TTS_TIMEOUT,
        TTS_FAILED."""
        if not text or not text.strip():
            return {"error": "TTS_EMPTY", "message": "nothing to speak"}

        cmd = ["termux-tts-speak", "-s", self.stream,
               "-r", str(self.rate), "-p", str(self.pitch)]

        def _run():
            return subprocess.run(cmd, input=text.encode(),
                                  capture_output=True, timeout=timeout_sec)

        try:
            proc = await asyncio.to_thread(_run)
        except FileNotFoundError:
            return {"error": "TTS_UNAVAILABLE",
                    "message": "termux-tts-speak not found (pkg install termux-api)"}
        except subprocess.TimeoutExpired:
            return {"error": "TTS_TIMEOUT",
                    "message": f"tts exceeded {timeout_sec:.0f}s"}
        if proc.returncode != 0:
            detail = (proc.stderr.decode(errors="replace").strip()[:200]
                      or f"termux-tts-speak exited {proc.returncode}")
            return {"error": "TTS_FAILED", "message": detail}
        return {"spoken": True, "chars": len(text)}
