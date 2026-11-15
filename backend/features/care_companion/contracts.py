from dataclasses import dataclass
from enum import StrEnum


class PersonaId(StrEnum):
    MOTHER = "mother-like"
    FATHER = "father-like"
    FRIEND = "best-friend"
    SIBLING = "sibling"
    GIRLFRIEND = "girlfriend"
    BOYFRIEND = "boyfriend"


class CallState(StrEnum):
    INCOMING = "incoming"
    ACTIVE = "active"
    DECLINED = "declined"
    ENDED = "ended"
    MISSED = "missed"


@dataclass(frozen=True)
class TranscriptEvent:
    role: str
    text: str
    timestamp: str


@dataclass(frozen=True)
class VoiceSession:
    session_id: str
    persona: PersonaId
    locale: str
    demo: bool
    state: str


class ProviderUnavailable(RuntimeError):
    pass
