"""phone.voice.ask — one-shot voice cycle (manual trigger, no wake word)."""

from tools.voice_common import get_session


def register(mcp):
    @mcp.tool(name="phone.voice.ask")
    async def voice_ask(text: str | None = None,
                        audio_path: str | None = None) -> dict:
        """Run one voice cycle. With `text`: route then speak. With
        `audio_path`: transcribe -> route -> speak. With neither: record ~15s
        -> transcribe -> route -> speak. Returns response, source
        (local | laptop | local_offline), and transcript. Errors:
        NO_AUDIO_SOURCE, NO_TRANSCRIBER, VOICE_TIMEOUT, VOICE_FAILED, plus any
        capture error (MICROPHONE_BUSY, VAD_TIMEOUT, ...) surfaced verbatim."""
        try:
            return await get_session().ask(audio_path=audio_path, text=text)
        except Exception as e:
            return {"error": "VOICE_FAILED", "message": str(e)[:200]}
