"""Provider-independent speech and language seams; app integration can wrap LiveKit AgentSession."""

from typing import Protocol


class STT(Protocol):
    async def transcribe(self, audio: bytes, locale: str) -> str: ...


class LLM(Protocol):
    async def respond(self, messages: list[dict[str, str]], persona: str, locale: str) -> str: ...


class TTS(Protocol):
    async def synthesize(self, text: str, voice: str, locale: str) -> bytes: ...


class VoiceProvidersUnavailable(RuntimeError):
    pass


class VoiceProviderSet:
    def __init__(self, stt=None, llm=None, tts=None):
        self.stt, self.llm, self.tts = stt, llm, tts

    def require(self):
        if not all((self.stt, self.llm, self.tts)):
            raise VoiceProvidersUnavailable(
                "Live voice unavailable: STT, conversation, and TTS providers must be configured"
            )
        return self
