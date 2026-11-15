from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CareerRequest(BaseModel):
    education_level: str = Field(min_length=1, max_length=100)
    interests: list[str] = Field(min_length=1, max_length=20)
    skills: list[str] = Field(default_factory=list, max_length=50)
    constraints: list[str] | None = Field(default=None, max_length=20)
    consent: bool = False

    @field_validator("constraints", mode="before")
    @classmethod
    def normalize_constraints(cls, value: object) -> object:
        # Keep the internal contract as list[str] while accepting the earlier UI object shape.
        if isinstance(value, dict):
            if len(value) > 20 or any(
                not isinstance(key, str) or not isinstance(item, str)
                for key, item in value.items()
            ):
                raise ValueError("constraints must contain at most 20 string key/value pairs")
            return [f"{key}: {item}" for key, item in value.items()]
        return value


class CareerItem(BaseModel):
    domain: str
    role: str
    specialization: str
    match_score: float
    rationale: list[str]
    skill_gaps: list[str]
    roadmap: list[str]


class CareerResponse(BaseModel):
    recommendations: list[CareerItem]
    taxonomy_version: str
    model_version: str
    generated_at: datetime
    limitations: list[str]
    demo: bool


class TutorSessionRequest(BaseModel):
    consent: bool = False
    topic: str = Field(min_length=1, max_length=200)
    duration_minutes: int = Field(ge=1, le=180)
    course_id: UUID | None = None


class TutorTurnRequest(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=5000)
    audio_ref: str | None = Field(default=None, max_length=500)


class VoiceSessionRequest(BaseModel):
    consent: bool = False
    mode: str = Field(pattern="^(practice|assistant|lesson)$")
    locale: str = Field(default="en", min_length=2, max_length=16)


class AvatarSessionRequest(BaseModel):
    consent: bool = False
    audio_stream_ref: str = Field(min_length=1, max_length=500)
    avatar_id: str = Field(min_length=1, max_length=100)


class DesktopSessionRequest(BaseModel):
    capabilities: list[str] = Field(min_length=1, max_length=10)
    consent_version: str = Field(min_length=1, max_length=40)


class FeatureSessionResponse(BaseModel):
    session_id: UUID
    state: str
    demo: bool
    expires_at: datetime | None = None
    transport: str | None = None
    token: str | None = None
    playback_url: str | None = None
    companion_challenge: str | None = None


class TutorTurnResponse(BaseModel):
    answer: str
    speech_ref: str | None = None
    board_events: list[dict[str, str | int | float]]
    demo: bool
