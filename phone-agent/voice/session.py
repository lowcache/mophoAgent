import asyncio

IDLE = "IDLE"
LISTENING = "LISTENING"
LISTENING_ACTIVE = "LISTENING_ACTIVE"
TRANSCRIBING = "TRANSCRIBING"
ROUTING = "ROUTING"
SPEAKING = "SPEAKING"

class VoiceSession:
    """
    Manages a voice interaction session state machine, from listening to routing and speaking.
    Possible errors include NO_AUDIO_SOURCE, NO_TRANSCRIBER, VOICE_TIMEOUT, and WAKE_WORD_UNAVAILABLE.
    """

    def __init__(
        self,
        router,
        tts,
        whisper=None,
        capture=None,
        wake_word=None,
        notify=None,
        state_timeout_sec: float = 30.0,
    ):
        self.router = router
        self.tts = tts
        self.whisper = whisper
        self.capture = capture
        self.wake_word = wake_word
        self.notify = notify
        self.state_timeout_sec = state_timeout_sec
        self.state = IDLE

    async def ask(self, audio_path: str | None = None, text: str | None = None) -> dict:
        try:
            if text is None:
                if audio_path is None:
                    if self.capture is None:
                        return {"error": "NO_AUDIO_SOURCE", "message": "No audio capture dependency provided"}
                    cap = await self.capture(max_duration_sec=15)
                    if isinstance(cap, dict) and cap.get("error"):
                        return cap
                    audio_path = cap["audio_path"]

                if self.whisper is None:
                    return {"error": "NO_TRANSCRIBER", "message": "No whisper transcription dependency provided"}

                self.state = TRANSCRIBING
                text = await asyncio.wait_for(
                    self.whisper.transcribe(audio_path),
                    self.state_timeout_sec
                )

            self.state = ROUTING
            response, source = await asyncio.wait_for(
                self.router.route(text),
                self.state_timeout_sec
            )

            self.state = SPEAKING
            # Speaking is best-effort: the response is already produced, so a
            # slow/wedged/broken TTS must not hold the call open or lose the
            # answer. (tts.speak already caps to a short preview; this bounds
            # it anyway.) The result is kept so callers can tell "spoke" from
            # "silently failed" without a listening test.
            try:
                spoken = await asyncio.wait_for(self.tts.speak(response),
                                                self.state_timeout_sec)
            except asyncio.TimeoutError:
                spoken = {"spoken": False, "error": "TTS_TIMEOUT",
                          "message": f"speak exceeded {self.state_timeout_sec:.0f}s"}
            except Exception as e:
                spoken = {"spoken": False, "error": "TTS_FAILED",
                          "message": str(e)[:200]}

            self.state = IDLE
            return {"response": response, "source": source, "transcript": text,
                    "spoken": spoken}

        except asyncio.TimeoutError:
            self.state = IDLE
            if self.notify:
                await self.notify("Voice session reset", "a step exceeded the timeout")
            return {
                "error": "VOICE_TIMEOUT",
                "message": f"a step exceeded {self.state_timeout_sec:.0f}s"
            }

    async def start(self, wake_word: str | None = None) -> dict:
        if self.wake_word is None:
            return {"error": "WAKE_WORD_UNAVAILABLE", "message": "no detector configured"}
        self.state = LISTENING
        self.wake_word.listen(self._on_wake_sync)
        return {"status": "listening"}

    def _on_wake_sync(self):
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._on_wake())
        except Exception:
            pass

    async def _on_wake(self):
        self.state = LISTENING_ACTIVE
        await self.ask()
        self.state = LISTENING

    def stop(self) -> dict:
        self.state = IDLE
        return {"status": "stopped"}
