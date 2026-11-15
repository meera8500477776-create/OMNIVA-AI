"""Stable stdlib typed request/response schemas for Phase 1 adapter endpoints."""
from __future__ import annotations

from typing import NotRequired, TypedDict


API_PREFIX = "/api/v1"
FEATURE_PATHS = {
    "career_recommendations": f"{API_PREFIX}/features/career/recommendations",
    "tutor_sessions": f"{API_PREFIX}/features/tutor/sessions",
    "tutor_turns": f"{API_PREFIX}/features/tutor/sessions/{{session_id}}/turns",
    "voice_sessions": f"{API_PREFIX}/features/voice/sessions",
    "avatar_sessions": f"{API_PREFIX}/features/avatar/sessions",
    "desktop_sessions": f"{API_PREFIX}/features/desktop/sessions",
}


class ErrorDetail(TypedDict):
    code: str
    message: str
    request_id: str


class ErrorEnvelope(TypedDict):
    error: ErrorDetail


class CareerRecommendationRequest(TypedDict):
    education_level: str
    interests: list[str]
    skills: list[str]
    constraints: NotRequired[list[str]]


class CareerMatch(TypedDict):
    domain: str
    role: str
    specialization: str
    match_score: int
    rationale: list[str]
    skill_gaps: list[str]
    roadmap: list[str]


class CareerRecommendationResponse(TypedDict):
    recommendations: list[CareerMatch]
    taxonomy_version: str
    ruleset_version: str
    generated_at: str
    limitations: list[str]


class TutorSessionRequest(TypedDict):
    topic: str
    duration_minutes: int
    course_id: NotRequired[str | None]


class TutorSessionResponse(TypedDict):
    session_id: str
    state: str


class TutorTurnRequest(TypedDict):
    text: NotRequired[str]
    audio_ref: NotRequired[str | None]


class BoardEventPayload(TypedDict):
    kind: str
    x: int
    y: int
    text: str
    x2: NotRequired[int | None]
    y2: NotRequired[int | None]


class TutorTurnResponse(TypedDict):
    answer: str
    speech_ref: str | None
    board_events: list[BoardEventPayload]


class VoiceSessionRequest(TypedDict):
    mode: str
    locale: str


class VoiceSessionResponse(TypedDict):
    session_id: str
    transport: str
    token: str | None
    expires_at: str | None


class TranscriptEvent(TypedDict):
    type: str
    speaker: str
    text: str
    final: bool
    sequence: int
    created_at: str


class DesktopSessionRequest(TypedDict):
    capabilities: list[str]
    consent_version: str


class DesktopSessionResponse(TypedDict):
    session_id: str
    companion_challenge: str


class AvatarSessionRequest(TypedDict):
    audio_stream_ref: str
    avatar_id: str


class AvatarSessionResponse(TypedDict):
    session_id: str
    playback_url: NotRequired[str | None]
