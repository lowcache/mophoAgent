"""Local text-to-speech via Android's system TTS engine (termux-tts-speak).

No cloud TTS (charter guardrail): termux-tts-speak drives the on-device engine
(Google/Samsung). Text is fed on stdin, never as an argv, so long responses and
shell-special characters need no quoting. Volume is left to the phone's media
stream — we never force it up. Long answers are spoken as a capped preview (the
caller still returns the full response), so a complex reply is not read aloud in
full.
"""

import asyncio
import subprocess

_DEFAULT_MAX_SPEAK_CHARS = 350


def truncate_for_speech(text: str, max_chars: int) -> tuple[str, bool]:
    """Trim `text` to a spoken preview of at most ~max_chars, cutting at the last
    sentence boundary in the back half so speech ends on a whole sentence rather
    than mid-word. Returns (spoken_text, truncated). max_chars <= 0 disables
    truncation (speak everything)."""
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    head = text[:max_chars]
    cut = max(head.rfind(". "), head.rfind("! "), head.rfind("? "),
              head.rfind(".\n"), head.rfind("\n"))
    if cut >= max_chars // 2:
        head = head[:cut + 1]
    return head.rstrip() + " … full response returned.", True


class TTSEngine:
    def __init__(self, rate: float = 1.0, pitch: float = 1.0, stream: str = "MUSIC",
                 max_chars: int = _DEFAULT_MAX_SPEAK_CHARS):
        # stream MUSIC ties playback to the media volume the user already set.
        self.rate = rate
        self.pitch = pitch
        self.stream = stream
        self.max_chars = max_chars

    async def speak(self, text: str, timeout_sec: float = 45.0,
                    max_chars: int | None = None) -> dict:
        """Speak `text` through the system TTS engine, blocking until playback
        finishes. Only a preview of at most ~max_chars (engine default 350) is
        spoken so a long answer is not read in full — the caller still returns
        the whole response. Returns {"spoken": True, "chars": <spoken>,
        "truncated": <bool>}. Errors: TTS_EMPTY, TTS_UNAVAILABLE
        (termux-tts-speak not installed), TTS_TIMEOUT, TTS_FAILED."""
        if not text or not text.strip():
            return {"error": "TTS_EMPTY", "message": "nothing to speak"}

        limit = self.max_chars if max_chars is None else max_chars
        spoken, truncated = truncate_for_speech(text, limit)

        cmd = ["termux-tts-speak", "-s", self.stream,
               "-r", str(self.rate), "-p", str(self.pitch)]

        def _run():
            return subprocess.run(cmd, input=spoken.encode(),
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
        return {"spoken": True, "chars": len(spoken), "truncated": truncated}
