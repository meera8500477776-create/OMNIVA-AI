from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class RoleName(StrEnum):
    student = "student"
    instructor = "instructor"
    admin = "admin"


class UserRole(SQLModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True, ondelete="CASCADE")
    role: RoleName = Field(primary_key=True)


class User(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("email", name="uq_user_email"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True, max_length=255)
    display_name: str = Field(max_length=120)
    password_hash: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    roles: list[UserRole] = Relationship(cascade_delete=True)


class AuthSession(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    refresh_hash: str = Field(index=True, unique=True, max_length=64)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime = Field(index=True)
    revoked_at: datetime | None = None


class PasswordReset(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    token_hash: str = Field(index=True, unique=True, max_length=64)
    expires_at: datetime = Field(index=True)
    consumed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Course(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    slug: str = Field(unique=True, index=True, max_length=120)
    title: str = Field(max_length=200)
    description: str = Field(default="", max_length=2000)
    published: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    modules: list[Module] = Relationship(back_populates="course", cascade_delete=True)


class Module(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("course_id", "position", name="uq_module_course_position"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    course_id: UUID = Field(foreign_key="course.id", index=True, ondelete="CASCADE")
    title: str = Field(max_length=200)
    position: int = Field(ge=0)
    course: Course = Relationship(back_populates="modules")
    lessons: list[Lesson] = Relationship(back_populates="module", cascade_delete=True)


class Lesson(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("module_id", "position", name="uq_lesson_module_position"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    module_id: UUID = Field(foreign_key="module.id", index=True, ondelete="CASCADE")
    title: str = Field(max_length=200)
    content: str = Field(default="", max_length=20000)
    duration_seconds: int = Field(default=0, ge=0)
    position: int = Field(ge=0)
    module: Module = Relationship(back_populates="lessons")


class Enrollment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_enrollment_user_course"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    course_id: UUID = Field(foreign_key="course.id", index=True, ondelete="CASCADE")
    enrolled_at: datetime = Field(default_factory=utcnow)


class LessonProgress(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_progress_user_lesson"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    lesson_id: UUID = Field(foreign_key="lesson.id", index=True, ondelete="CASCADE")
    status: str = Field(default="not_started", max_length=20)
    position_seconds: int = Field(default=0, ge=0)
    updated_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None


class QuizAttempt(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    lesson_id: UUID = Field(foreign_key="lesson.id", index=True, ondelete="CASCADE")
    score: float = Field(ge=0, le=1)
    answers: str = Field(default="{}", max_length=10000)
    created_at: datetime = Field(default_factory=utcnow)


class FeatureSession(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    feature: str = Field(index=True, max_length=40)
    state: str = Field(max_length=30)
    demo: bool = False
    consent_version: str | None = None
    metadata_json: str = Field(default="{}", max_length=10000)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None


class TutorMessage(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    session_id: UUID = Field(foreign_key="featuresession.id", index=True, ondelete="CASCADE")
    role: str = Field(max_length=20)
    body: str = Field(max_length=5000)
    created_at: datetime = Field(default_factory=utcnow)


class CareerRecommendation(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    model_version: str = Field(max_length=80)
    taxonomy_version: str = Field(max_length=80)
    result_json: str = Field(max_length=20000)
    created_at: datetime = Field(default_factory=utcnow)


class CareReminder(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_care_reminder_user_key"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    title: str = Field(max_length=120)
    body: str = Field(max_length=500)
    reminder_type: str = Field(default="deadline", max_length=30)
    scheduled_at: datetime = Field(index=True)
    timezone_name: str = Field(max_length=80)
    quiet_start: str = Field(max_length=5)
    quiet_end: str = Field(max_length=5)
    idempotency_key: str = Field(max_length=100)
    status: str = Field(default="scheduled", max_length=20, index=True)
    fired_at: datetime | None = None
    acknowledged_at: datetime | None = None
    push_status: str = Field(default="pending", max_length=20)
    push_attempted_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class CarePushSubscription(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("endpoint_hash", name="uq_care_push_endpoint_hash"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    endpoint_hash: str = Field(index=True, max_length=64)
    encrypted_subscription: str = Field(max_length=12000)
    created_at: datetime = Field(default_factory=utcnow)


class AuditEvent(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    actor_id: UUID | None = Field(
        default=None, foreign_key="user.id", index=True, ondelete="SET NULL"
    )
    action: str = Field(index=True, max_length=100)
    resource_type: str = Field(max_length=80)
    resource_id: str | None = Field(default=None, max_length=100)
    request_id: str | None = Field(default=None, max_length=80)
    safe_metadata: str = Field(default="{}", max_length=4000)
    occurred_at: datetime = Field(default_factory=utcnow, index=True)
