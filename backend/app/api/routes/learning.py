import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.db.models import (
    AuditEvent,
    Course,
    Enrollment,
    Lesson,
    LessonProgress,
    Module,
    QuizAttempt,
)
from app.schemas.learning import (
    CourseOut,
    CoursePage,
    LessonOut,
    ProgressOut,
    ProgressPage,
    ProgressUpdate,
    QuizAttemptCreate,
)

router = APIRouter(tags=["learning"])


def course_to_out(course: Course) -> CourseOut:
    modules = sorted(course.modules, key=lambda item: item.position)
    return CourseOut(
        id=course.id,
        slug=course.slug,
        title=course.title,
        description=course.description,
        modules=[
            {
                "id": module.id,
                "title": module.title,
                "position": module.position,
                "lessons": [
                    LessonOut.model_validate(lesson)
                    for lesson in sorted(module.lessons, key=lambda item: item.position)
                ],
            }
            for module in modules
        ],
    )


@router.get("/courses", response_model=CoursePage)
def list_courses(
    current_user: CurrentUser,
    session: SessionDep,
    limit: int = Query(20, ge=1, le=100),
    cursor: UUID | None = None,
) -> CoursePage:
    query = (
        select(Course)
        .where(Course.published.is_(True))
        .options(selectinload(Course.modules).selectinload(Module.lessons))
        .order_by(Course.id)
        .limit(limit + 1)
    )
    if cursor:
        query = query.where(Course.id > cursor)
    courses = session.exec(query).unique().all()
    has_more = len(courses) > limit
    courses = courses[:limit]
    return CoursePage(
        items=[course_to_out(course) for course in courses],
        next_cursor=str(courses[-1].id) if has_more and courses else None,
    )


@router.get("/courses/{course_id}", response_model=CourseOut)
def get_course(course_id: UUID, current_user: CurrentUser, session: SessionDep) -> CourseOut:
    course = (
        session.exec(
            select(Course)
            .where(Course.id == course_id, Course.published.is_(True))
            .options(selectinload(Course.modules).selectinload(Module.lessons))
        )
        .unique()
        .first()
    )
    if course is None:
        raise HTTPException(
            status_code=404, detail={"code": "course_not_found", "message": "Course not found"}
        )
    return course_to_out(course)


@router.get("/lessons/{lesson_id}", response_model=LessonOut)
def get_lesson(lesson_id: UUID, current_user: CurrentUser, session: SessionDep) -> LessonOut:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(
            status_code=404, detail={"code": "lesson_not_found", "message": "Lesson not found"}
        )
    module = session.get(Module, lesson.module_id)
    course = session.get(Course, module.course_id) if module else None
    enrolled = (
        session.exec(
            select(Enrollment).where(
                Enrollment.user_id == current_user.id, Enrollment.course_id == course.id
            )
        ).first()
        if course
        else None
    )
    if course is None or not course.published or enrolled is None:
        raise HTTPException(
            status_code=404, detail={"code": "lesson_not_found", "message": "Lesson not found"}
        )
    return LessonOut.model_validate(lesson)


@router.post("/courses/{course_id}/enroll", status_code=201)
def enroll(
    course_id: UUID, current_user: CurrentUser, session: SessionDep
) -> dict[str, str | UUID]:
    course = session.get(Course, course_id)
    if course is None or not course.published:
        raise HTTPException(
            status_code=404, detail={"code": "course_not_found", "message": "Course not found"}
        )
    enrollment = session.exec(
        select(Enrollment).where(
            Enrollment.user_id == current_user.id, Enrollment.course_id == course_id
        )
    ).first()
    if enrollment is None:
        enrollment = Enrollment(user_id=current_user.id, course_id=course_id)
        session.add(enrollment)
        session.commit()
        session.refresh(enrollment)
    return {"id": enrollment.id, "course_id": course_id, "status": "enrolled"}


@router.get("/me/progress", response_model=ProgressPage)
def get_progress(
    current_user: CurrentUser,
    session: SessionDep,
    course_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: UUID | None = None,
) -> ProgressPage:
    query = (
        select(LessonProgress)
        .where(LessonProgress.user_id == current_user.id)
        .order_by(LessonProgress.lesson_id)
        .limit(limit + 1)
    )
    if cursor:
        query = query.where(LessonProgress.lesson_id > cursor)
    if course_id:
        lesson_ids = select(Lesson.id).join(Module).where(Module.course_id == course_id)
        query = query.where(LessonProgress.lesson_id.in_(lesson_ids))
    progress = session.exec(query).all()
    more = len(progress) > limit
    progress = progress[:limit]
    return ProgressPage(
        items=[
            ProgressOut(
                lesson_id=p.lesson_id,
                status=p.status,
                position_seconds=p.position_seconds,
                updated_at=p.updated_at,
            )
            for p in progress
        ],
        next_cursor=str(progress[-1].lesson_id) if more and progress else None,
    )


@router.put("/me/progress/{lesson_id}", response_model=ProgressOut)
def update_progress(
    lesson_id: UUID, payload: ProgressUpdate, current_user: CurrentUser, session: SessionDep
) -> ProgressOut:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(
            status_code=404, detail={"code": "lesson_not_found", "message": "Lesson not found"}
        )
    module = session.get(Module, lesson.module_id)
    enrollment = session.exec(
        select(Enrollment).where(
            Enrollment.user_id == current_user.id,
            Enrollment.course_id == module.course_id if module else None,
        )
    ).first()
    if enrollment is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "enrollment_required",
                "message": "Enroll in this course to update progress",
            },
        )
    progress = session.exec(
        select(LessonProgress)
        .where(LessonProgress.user_id == current_user.id, LessonProgress.lesson_id == lesson_id)
        .with_for_update()
    ).first()
    if progress is None:
        progress = LessonProgress(user_id=current_user.id, lesson_id=lesson_id)
    progress.status = payload.status
    progress.position_seconds = payload.position_seconds
    progress.updated_at = datetime.now(UTC)
    progress.completed_at = datetime.now(UTC) if payload.status == "completed" else None
    session.add(progress)
    session.commit()
    session.refresh(progress)
    return ProgressOut(
        lesson_id=progress.lesson_id,
        status=progress.status,
        position_seconds=progress.position_seconds,
        updated_at=progress.updated_at,
    )


@router.post("/quizzes/attempts", status_code=201)
def record_quiz_attempt(
    payload: QuizAttemptCreate, current_user: CurrentUser, session: SessionDep
) -> dict[str, str | UUID | float]:
    lesson = session.get(Lesson, payload.lesson_id)
    if lesson is None:
        raise HTTPException(
            status_code=404, detail={"code": "lesson_not_found", "message": "Lesson not found"}
        )
    module = session.get(Module, lesson.module_id)
    enrollment = session.exec(
        select(Enrollment).where(
            Enrollment.user_id == current_user.id,
            Enrollment.course_id == module.course_id if module else None,
        )
    ).first()
    if enrollment is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "enrollment_required",
                "message": "Enroll in this course to submit a quiz",
            },
        )
    attempt = QuizAttempt(
        user_id=current_user.id,
        lesson_id=lesson.id,
        score=payload.score,
        answers=json.dumps(payload.answers, separators=(",", ":")),
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return {
        "id": attempt.id,
        "lesson_id": attempt.lesson_id,
        "score": attempt.score,
        "created_at": attempt.created_at.isoformat(),
    }


@router.get("/me/enrollments")
def list_enrollments(current_user: CurrentUser, session: SessionDep) -> dict:
    enrollments = session.exec(
        select(Enrollment)
        .where(Enrollment.user_id == current_user.id)
        .order_by(Enrollment.enrolled_at.desc())
    ).all()
    return {
        "items": [
            {"id": item.id, "course_id": item.course_id, "enrolled_at": item.enrolled_at}
            for item in enrollments
        ]
    }


@router.delete("/me/enrollments/{course_id}", status_code=204)
def withdraw(course_id: UUID, current_user: CurrentUser, session: SessionDep) -> None:
    enrollment = session.exec(
        select(Enrollment)
        .where(Enrollment.user_id == current_user.id, Enrollment.course_id == course_id)
        .with_for_update()
    ).first()
    if enrollment is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "enrollment_not_found", "message": "Enrollment not found"},
        )
    session.add(
        AuditEvent(
            actor_id=current_user.id,
            action="course.withdraw",
            resource_type="enrollment",
            resource_id=str(enrollment.id),
        )
    )
    session.delete(enrollment)
    session.commit()
