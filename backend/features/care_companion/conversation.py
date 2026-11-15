import asyncio
import uuid

from .contracts import PersonaId, VoiceSession
from .demo_provider import DemoCompanion
from .personas import PERSONAS
from .voice_adapter import VoiceProviderSet, VoiceProvidersUnavailable


class Conversation:
    def __init__(self, *, demo=True, providers=None, timeout=5):
        self.demo, self.providers, self.timeout = demo, providers or VoiceProviderSet(), timeout
        self.sessions = {}
        self.transcripts = {}

    async def start(self, persona: PersonaId, locale="en") -> VoiceSession:
        if locale.split("-")[0].casefold() not in {"en", "te"}:
            raise ValueError("Supported demo locales are en and te")
        if not self.demo and self.providers.llm is None:
            raise VoiceProvidersUnavailable(
                "Live conversation unavailable: the language model provider is not configured"
            )
        sid = str(uuid.uuid4())
        s = VoiceSession(sid, persona, locale, self.demo, "active")
        self.sessions[sid] = s
        self.transcripts[sid] = []
        return s

    async def reply(self, sid, text):
        s = self.sessions[sid]
        if s.state != "active":
            raise ValueError("Session is not active")
        if self.demo:
            answer = DemoCompanion().reply(s.persona, text, s.locale)
        else:
            history = [
                {"role": item["role"], "content": item["text"]}
                for item in self.transcripts[sid][-10:]
            ]
            history.append({"role": "user", "content": text})
            answer = await asyncio.wait_for(
                self.providers.llm.respond(
                    history, PERSONAS[s.persona].style, s.locale
                ),
                self.timeout,
            )
        self.transcripts[sid].extend(
            [{"role": "user", "text": text}, {"role": "assistant", "text": answer}]
        )
        return answer

    def switch(self, sid, persona):
        self.sessions[sid] = VoiceSession(
            sid, persona, self.sessions[sid].locale, self.demo, self.sessions[sid].state
        )
