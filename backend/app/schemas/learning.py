from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LessonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    content: str
    duration_seconds: int
    position: int


class ModuleOut(BaseModel):
    id: UUID
    title: str
    position: int
    lessons: list[LessonOut]


class CourseOut(BaseModel):
    id: UUID
    slug: str
    title: str
    description: str
    modules: list[ModuleOut]


class CoursePage(BaseModel):
    items: list[CourseOut]
    next_cursor: str | None = None


class ProgressUpdate(BaseModel):
    status: str = Field(pattern="^(not_started|in_progress|completed)$")
    position_seconds: int = Field(ge=0, le=86400)


class ProgressOut(BaseModel):
    lesson_id: UUID
    status: str
    position_seconds: int
    updated_at: datetime


class ProgressPage(BaseModel):
    items: list[ProgressOut]
    next_cursor: str | None = None


class QuizAttemptCreate(BaseModel):
    lesson_id: UUID
    score: float = Field(ge=0, le=1)
    answers: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
