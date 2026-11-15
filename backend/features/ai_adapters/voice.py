"""Provider-independent voice orchestration with deterministic offline behavior."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol

from .common import AdapterError, Mode, RuntimeConfig, new_id, run_bounded, utc_now


class STTProvider(Protocol):
    async def transcribe(self, audio: bytes, locale: str) -> str: ...


class DialogueProvider(Protocol):
    async def respond(self, text: str, locale: str, history: list[dict[str, str]]) -> str: ...


class TTSProvider(Protocol):
    async def synthesize(self, text: str, locale: str) -> str: ...


class VoiceTransportIssuer(Protocol):
    async def create_session(
        self, session_id: str, user_id: str, locale: str
    ) -> dict[str, object]: ...
    async def end_session(self, session_id: str) -> None: ...
    async def cancel_session(self, session_id: str) -> None: ...


@dataclass(slots=True)
class VoiceSession:
    session_id: str
    user_id: str
    locale: str
    mode: Mode
    state: str = "active"
    transport: str = "simulation"
    conversation: list[dict[str, str]] = field(default_factory=list)
    events: list[dict[str, object]] = field(default_factory=list)
    sequence: int = 0
    audio_ref: str | None = None
    in_flight: asyncio.Task[object] | None = None


class VoiceAdapter:
    def __init__(
        self,
        config: RuntimeConfig | None = None,
        stt: STTProvider | None = None,
        dialogue: DialogueProvider | None = None,
        tts: TTSProvider | None = None,
        transport_issuer: VoiceTransportIssuer | None = None,
    ) -> None:
        self.config = config or RuntimeConfig()
        self.stt, self.dialogue, self.tts = stt, dialogue, tts
        self.transport_issuer = transport_issuer
        self.sessions: dict[str, VoiceSession] = {}

    async def create_session(
        self, user_id: str, mode: Mode | None = None, locale: str = "en"
    ) -> dict[str, object]:
        selected = mode or self.config.default_mode
        session_id = new_id()
        if selected == Mode.DEMO:
            transport = "simulation"
        else:
            if self.transport_issuer is None:
                raise AdapterError(
                    "provider_unavailable",
                    "Live voice transport/token issuer is not configured",
                    503,
                )
            issued = await run_bounded(
                self.transport_issuer.create_session(session_id, user_id, locale),
                self.config.provider_timeout_seconds,
                "voice_transport",
            )
            token, expires_at, transport = (
                issued.get("token"),
                issued.get("expires_at"),
                issued.get("transport"),
            )
            if (
                not isinstance(token, str)
                or not token
                or not isinstance(expires_at, str)
                or not isinstance(transport, str)
            ):
                raise AdapterError(
                    "invalid_provider_output",
                    "Voice transport issuer returned an invalid session",
                    502,
                )
        session = VoiceSession(session_id, user_id, locale, selected, transport=transport)
        self.sessions[session_id] = session
        return {
            "session_id": session_id,
            "transport": transport,
            "token": None if selected == Mode.DEMO else token,
            "expires_at": None if selected == Mode.DEMO else expires_at,
            "state": session.state,
            "mode": selected.value,
        }

    async def submit_text(self, session_id: str, text: str) -> dict[str, object]:
        session = self._active(session_id)
        clean = text.strip()
        if not clean or len(clean) > 4000:
            raise AdapterError("invalid_message", "Text must contain 1 to 4000 characters", 422)
        if session.mode == Mode.LIVE and (self.dialogue is None or self.tts is None):
            raise AdapterError(
                "provider_unavailable", "Live voice dialogue and TTS providers are required", 503
            )
        self._event(session, "transcript", "user", clean, final=True)
        session.conversation.append({"role": "user", "text": clean})
        if session.mode == Mode.DEMO:
            answer = f"Demo heard: {clean}"
        else:
            task = asyncio.current_task()
            session.in_flight = task
            try:
                answer = await run_bounded(
                    self.dialogue.respond(clean, session.locale, list(session.conversation)),
                    self.config.provider_timeout_seconds,
                    "voice",
                )
                if not isinstance(answer, str) or not answer.strip():
                    raise AdapterError(
                        "invalid_provider_output", "Live voice provider returned no response", 502
                    )
                session.conversation.append({"role": "assistant", "text": answer})
                self._event(session, "transcript", "assistant", answer, final=True)
                session.audio_ref = await run_bounded(
                    self.tts.synthesize(answer, session.locale),
                    self.config.provider_timeout_seconds,
                    "voice_tts",
                )
                return {
                    "session_id": session_id,
                    "answer": answer,
                    "audio_ref": session.audio_ref,
                    "events": list(session.events[-2:]),
                    "state": session.state,
                    "mode": session.mode.value,
                    "simulation": False,
                }
            finally:
                if session.in_flight is task:
                    session.in_flight = None
        session.conversation.append({"role": "assistant", "text": answer})
        self._event(session, "transcript", "assistant", answer, final=True)
        return {
            "session_id": session_id,
            "answer": answer,
            "audio_ref": None,
            "events": list(session.events[-2:]),
            "state": session.state,
            "mode": session.mode.value,
            "simulation": True,
        }

    async def submit_audio(self, session_id: str, audio: bytes) -> dict[str, object]:
        session = self._active(session_id)
        if not audio or len(audio) > 10_000_000:
            raise AdapterError("invalid_audio", "Audio payload is empty or exceeds 10 MB", 422)
        if session.mode == Mode.DEMO:
            transcript = "offline sample greeting"
        else:
            if self.stt is None:
                raise AdapterError(
                    "provider_unavailable", "Live voice STT provider is not configured", 503
                )
            task = asyncio.current_task()
            session.in_flight = task
            try:
                transcript = await run_bounded(
                    self.stt.transcribe(audio, session.locale),
                    self.config.provider_timeout_seconds,
                    "voice_stt",
                )
            finally:
                if session.in_flight is task:
                    session.in_flight = None
            if not isinstance(transcript, str) or not transcript.strip():
                raise AdapterError(
                    "invalid_provider_output", "Live STT provider returned no transcript", 502
                )
        result = await self.submit_text(session_id, transcript)
        result["transcript_source"] = "simulated" if session.mode == Mode.DEMO else "provider"
        return result

    def interrupt(self, session_id: str) -> dict[str, object]:
        session = self._active(session_id)
        if session.in_flight is not None and session.in_flight is not asyncio.current_task():
            session.in_flight.cancel()
        self._event(session, "interruption", "user", "", final=True)
        return {"session_id": session_id, "state": session.state, "events": [session.events[-1]]}

    async def cancel_session(self, session_id: str) -> dict[str, object]:
        session = self._get(session_id)
        session.state = "cancelled"
        if session.in_flight is not None and session.in_flight is not asyncio.current_task():
            session.in_flight.cancel()
        self._event(session, "cancelled", "system", "", final=True)
        session.audio_ref = None
        if self.transport_issuer is not None and session.mode == Mode.LIVE:
            await run_bounded(
                self.transport_issuer.cancel_session(session_id),
                self.config.provider_timeout_seconds,
                "voice_transport",
            )
        return {"session_id": session_id, "state": "cancelled"}

    async def end_session(self, session_id: str) -> dict[str, object]:
        session = self._get(session_id)
        if (
            session.state == "active"
            and session.in_flight is not None
            and session.in_flight is not asyncio.current_task()
        ):
            session.in_flight.cancel()
        session.state = "ended"
        self._event(session, "end", "system", "", final=True)
        session.audio_ref = None
        if self.transport_issuer is not None and session.mode == Mode.LIVE:
            await run_bounded(
                self.transport_issuer.end_session(session_id),
                self.config.provider_timeout_seconds,
                "voice_transport",
            )
        return {"session_id": session_id, "state": "ended", "ended_at": utc_now()}

    def status(self, session_id: str) -> dict[str, object]:
        session = self._get(session_id)
        return {
            "session_id": session_id,
            "state": session.state,
            "mode": session.mode.value,
            "transport": session.transport,
            "turn_count": len(session.conversation) // 2,
        }

    def _event(
        self, session: VoiceSession, kind: str, speaker: str, text: str, final: bool
    ) -> None:
        session.sequence += 1
        session.events.append(
            {
                "type": kind,
                "speaker": speaker,
                "text": text,
                "final": final,
                "sequence": session.sequence,
                "created_at": utc_now(),
            }
        )

    def _get(self, session_id: str) -> VoiceSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise AdapterError("session_not_found", "Voice session was not found", 404)
        return session

    def _active(self, session_id: str) -> VoiceSession:
        session = self._get(session_id)
        if session.state != "active":
            raise AdapterError("session_state_conflict", "Voice session is not active", 409)
        return session
