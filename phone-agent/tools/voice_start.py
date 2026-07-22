"""phone.voice.start — start a wake-word listening session (experimental)."""

from tools.voice_common import get_session


def register(mcp):
    @mcp.tool(name="phone.voice.start")
    async def voice_start(wake_word: str = "hey phone") -> dict:
        """Start a wake-word listening session. EXPERIMENTAL: no detector is
        wired by default (continuous Termux mic streaming is unreliable and
        contends with phone.capture.audio), so this returns
        WAKE_WORD_UNAVAILABLE until an OpenWakeWord model is installed and
        wired. On success returns {"status": "listening"}."""
        return await get_session().start(wake_word)
