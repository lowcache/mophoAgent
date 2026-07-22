"""phone.voice.stop — stop the voice session and return to IDLE."""

from tools.voice_common import get_session


def register(mcp):
    @mcp.tool(name="phone.voice.stop")
    async def voice_stop() -> dict:
        """Stop the voice session (wake-word listening off, state -> IDLE).
        Returns {"status": "stopped"}."""
        return get_session().stop()
