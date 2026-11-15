from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.api.routes.auth import user_public
from app.db.models import AuditEvent, Course, Lesson, Module, RoleName, User, UserRole
from app.schemas.admin import (
    CourseCreate,
    CoursePatch,
    LessonCreate,
    LessonPatch,
    ModuleCreate,
    ModulePatch,
)
from app.schemas.auth import ProfileUpdate
from app.schemas.common import UserPublic

router = APIRouter(tags=["users", "administration"])


@router.get("/users/me", response_model=UserPublic)
def get_me(user: CurrentUser, session: SessionDep) -> UserPublic:
    return user_public(user, session)


@router.patch("/users/me", response_model=UserPublic)
def patch_me(payload: ProfileUpdate, user: CurrentUser, session: SessionDep) -> UserPublic:
    # Profile fields remain narrowly scoped; never accept user ID or role changes here.
    display_name = payload.display_name
    if display_name is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_profile", "message": "display_name is required"},
        )
    if not isinstance(display_name, str) or not 1 <= len(display_name.strip()) <= 120:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_profile",
                "message": "Display name must be 1 to 120 characters",
            },
        )
    user.display_name = display_name.strip()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user_public(user, session)


def admin_only(user: CurrentUser, session: SessionDep) -> User:
    roles = set(session.exec(select(UserRole.role).where(UserRole.user_id == user.id)).all())
    if RoleName.admin not in roles:
        raise HTTPException(
            status_code=403, detail={"code": "forbidden", "message": "Administrator role required"}
        )
    return user


AdminUser = Depends(admin_only)


@router.post("/admin/courses", status_code=201)
def create_course(
    payload: CourseCreate, session: SessionDep, user: User = Depends(admin_only)
) -> dict:
    course = Course(
        slug=payload.slug,
        title=payload.title,
        description=payload.description,
        published=payload.published,
    )
    session.add(course)
    session.flush()
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="course.create",
            resource_type="course",
            resource_id=str(course.id),
        )
    )
    session.commit()
    session.refresh(course)
    return {
        "id": course.id,
        "slug": course.slug,
        "title": course.title,
        "description": course.description,
        "published": course.published,
    }


@router.post("/admin/courses/{course_id}/modules", status_code=201)
def create_module(
    course_id: UUID, payload: ModuleCreate, session: SessionDep, user: User = Depends(admin_only)
) -> dict:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(
            status_code=404, detail={"code": "course_not_found", "message": "Course not found"}
        )
    module = Module(course_id=course_id, title=payload.title, position=payload.position)
    session.add(module)
    session.flush()
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="course.module.create",
            resource_type="module",
            resource_id=str(module.id),
        )
    )
    session.commit()
    return {
        "id": module.id,
        "course_id": course_id,
        "title": module.title,
        "position": module.position,
    }


@router.post("/admin/modules/{module_id}/lessons", status_code=201)
def create_lesson(
    module_id: UUID, payload: LessonCreate, session: SessionDep, user: User = Depends(admin_only)
) -> dict:
    module = session.get(Module, module_id)
    if module is None:
        raise HTTPException(
            status_code=404, detail={"code": "module_not_found", "message": "Module not found"}
        )
    lesson = Lesson(
        module_id=module_id,
        title=payload.title,
        content=payload.content,
        duration_seconds=payload.duration_seconds,
        position=payload.position,
    )
    session.add(lesson)
    session.flush()
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="course.lesson.create",
            resource_type="lesson",
            resource_id=str(lesson.id),
        )
    )
    session.commit()
    return {
        "id": lesson.id,
        "module_id": module_id,
        "title": lesson.title,
        "content": lesson.content,
        "duration_seconds": lesson.duration_seconds,
        "position": lesson.position,
    }


@router.patch("/admin/courses/{course_id}")
def update_course(
    course_id: UUID, payload: CoursePatch, session: SessionDep, user: User = Depends(admin_only)
) -> dict:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(
            status_code=404, detail={"code": "course_not_found", "message": "Course not found"}
        )
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, key, value)
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="course.update",
            resource_type="course",
            resource_id=str(course.id),
        )
    )
    session.commit()
    session.refresh(course)
    return {
        "id": course.id,
        "slug": course.slug,
        "title": course.title,
        "description": course.description,
        "published": course.published,
    }


@router.delete("/admin/courses/{course_id}", status_code=204)
def delete_course(course_id: UUID, session: SessionDep, user: User = Depends(admin_only)) -> None:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(
            status_code=404, detail={"code": "course_not_found", "message": "Course not found"}
        )
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="course.delete",
            resource_type="course",
            resource_id=str(course.id),
        )
    )
    session.delete(course)
    session.commit()


@router.get("/admin/audit-events")
def list_audit_events(
    session: SessionDep, limit: int = 100, user: User = Depends(admin_only)
) -> dict:
    if not 1 <= limit <= 500:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_limit", "message": "limit must be between 1 and 500"},
        )
    events = session.exec(
        select(AuditEvent).order_by(AuditEvent.occurred_at.desc()).limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": event.id,
                "actor_id": event.actor_id,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "request_id": event.request_id,
                "occurred_at": event.occurred_at,
            }
            for event in events
        ]
    }


@router.patch("/admin/modules/{module_id}")
def update_module(
    module_id: UUID,
    payload: ModulePatch,
    session: SessionDep,
    user: User = Depends(admin_only),
) -> dict:
    module = session.get(Module, module_id)
    if module is None:
        raise HTTPException(
            status_code=404, detail={"code": "module_not_found", "message": "Module not found"}
        )
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(module, key, value)
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="course.module.update",
            resource_type="module",
            resource_id=str(module.id),
        )
    )
    session.commit()
    session.refresh(module)
    return {
        "id": module.id,
        "course_id": module.course_id,
        "title": module.title,
        "position": module.position,
    }


@router.delete("/admin/modules/{module_id}", status_code=204)
def delete_module(module_id: UUID, session: SessionDep, user: User = Depends(admin_only)) -> None:
    module = session.get(Module, module_id)
    if module is None:
        raise HTTPException(
            status_code=404, detail={"code": "module_not_found", "message": "Module not found"}
        )
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="course.module.delete",
            resource_type="module",
            resource_id=str(module.id),
        )
    )
    session.delete(module)
    session.commit()


@router.patch("/admin/lessons/{lesson_id}")
def update_lesson(
    lesson_id: UUID,
    payload: LessonPatch,
    session: SessionDep,
    user: User = Depends(admin_only),
) -> dict:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(
            status_code=404, detail={"code": "lesson_not_found", "message": "Lesson not found"}
        )
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(lesson, key, value)
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="course.lesson.update",
            resource_type="lesson",
            resource_id=str(lesson.id),
        )
    )
    session.commit()
    session.refresh(lesson)
    return {
        "id": lesson.id,
        "module_id": lesson.module_id,
        "title": lesson.title,
        "content": lesson.content,
        "duration_seconds": lesson.duration_seconds,
        "position": lesson.position,
    }


@router.delete("/admin/lessons/{lesson_id}", status_code=204)
def delete_lesson(lesson_id: UUID, session: SessionDep, user: User = Depends(admin_only)) -> None:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(
            status_code=404, detail={"code": "lesson_not_found", "message": "Lesson not found"}
        )
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="course.lesson.delete",
            resource_type="lesson",
            resource_id=str(lesson.id),
        )
    )
    session.delete(lesson)
    session.commit()
