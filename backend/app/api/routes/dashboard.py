from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.db.models import Course, Enrollment, LessonProgress, QuizAttempt

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(current_user: CurrentUser, session: SessionDep) -> dict:
    enrollments = session.exec(
        select(Enrollment).where(Enrollment.user_id == current_user.id)
    ).all()
    completed = session.exec(
        select(func.count())
        .select_from(LessonProgress)
        .where(LessonProgress.user_id == current_user.id, LessonProgress.status == "completed")
    ).one()
    active = session.exec(
        select(func.count())
        .select_from(LessonProgress)
        .where(LessonProgress.user_id == current_user.id, LessonProgress.status == "in_progress")
    ).one()
    attempts = session.exec(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.created_at.desc())
        .limit(10)
    ).all()
    course_ids = [e.course_id for e in enrollments]
    courses = (
        session.exec(select(Course).where(Course.id.in_(course_ids))).all() if course_ids else []
    )
    recent = session.exec(
        select(LessonProgress)
        .where(LessonProgress.user_id == current_user.id)
        .order_by(LessonProgress.updated_at.desc())
        .limit(10)
    ).all()
    return {
        "user": {"id": str(current_user.id), "display_name": current_user.display_name},
        "summary": {
            "enrolled_courses": len(enrollments),
            "completed_lessons": int(completed),
            "in_progress_lessons": int(active),
        },
        "courses": [{"id": str(c.id), "slug": c.slug, "title": c.title} for c in courses],
        "recent_progress": [
            {
                "lesson_id": str(p.lesson_id),
                "status": p.status,
                "position_seconds": p.position_seconds,
                "updated_at": p.updated_at.isoformat(),
            }
            for p in recent
        ],
        "recent_quiz_attempts": [
            {
                "id": str(a.id),
                "lesson_id": str(a.lesson_id),
                "score": a.score,
                "created_at": a.created_at.isoformat(),
            }
            for a in attempts
        ],
    }


@router.get("/analytics")
def analytics(current_user: CurrentUser, session: SessionDep, days: int = 30) -> dict:
    if not 1 <= days <= 365:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_days", "message": "days must be between 1 and 365"},
        )
    since = datetime.now(UTC) - timedelta(days=days)
    progress = session.exec(
        select(LessonProgress).where(
            LessonProgress.user_id == current_user.id, LessonProgress.updated_at >= since
        )
    ).all()
    attempts = session.exec(
        select(QuizAttempt).where(
            QuizAttempt.user_id == current_user.id, QuizAttempt.created_at >= since
        )
    ).all()
    return {
        "window_days": days,
        "progress_updates": len(progress),
        "completed_lessons": sum(1 for p in progress if p.status == "completed"),
        "quiz_attempts": len(attempts),
        "average_quiz_score": sum(a.score for a in attempts) / len(attempts) if attempts else None,
    }
