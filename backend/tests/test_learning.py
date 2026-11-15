from sqlmodel import select

from app.api.deps import get_session
from app.db.models import Course, Lesson, Module, RoleName, User, UserRole
from app.main import app


def auth(client, email="learn@example.com"):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "display_name": "Learner",
        },
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def course_fixture():
    course = Course(slug="test-course", title="Test Course", description="Tests")
    module = Module(title="Module One", position=0)
    lesson = Lesson(title="Lesson One", content="A lesson", duration_seconds=60, position=0)
    module.lessons = [lesson]
    course.modules = [module]
    return course, lesson


def test_courses_enrollment_and_progress(client):
    headers = auth(client)
    session = next(app.dependency_overrides[get_session]())
    course, lesson = course_fixture()
    session.add(course)
    session.commit()
    session.refresh(course)
    session.refresh(lesson)
    course_id, lesson_id = course.id, lesson.id
    session.close()
    listed = client.get("/api/v1/courses", headers=headers)
    assert listed.status_code == 200 and len(listed.json()["items"]) == 1
    assert client.get(f"/api/v1/lessons/{lesson_id}", headers=headers).status_code == 404
    assert client.post(f"/api/v1/courses/{course_id}/enroll", headers=headers).status_code == 201
    assert len(client.get("/api/v1/me/enrollments", headers=headers).json()["items"]) == 1
    updated = client.put(
        f"/api/v1/me/progress/{lesson_id}",
        headers=headers,
        json={"status": "completed", "position_seconds": 60},
    )
    assert updated.status_code == 200 and updated.json()["status"] == "completed"
    assert len(client.get("/api/v1/me/progress", headers=headers).json()["items"]) == 1
    assert (
        client.get("/api/v1/dashboard", headers=headers).json()["summary"]["completed_lessons"] == 1
    )
    assert client.get("/api/v1/dashboard/analytics", headers=headers).status_code == 200
    assert client.delete(f"/api/v1/me/enrollments/{course_id}", headers=headers).status_code == 204


def test_invalid_progress_and_unauthorized(client):
    assert client.get("/api/v1/courses").status_code == 401
    headers = auth(client)
    bad = client.put(
        "/api/v1/me/progress/00000000-0000-0000-0000-000000000001",
        headers={**headers, "X-Request-ID": "test-request-123"},
        json={"status": "bad", "position_seconds": -1},
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "validation_error"
    assert bad.json()["error"]["request_id"] == "test-request-123"


def test_admin_role_controls_catalog_crud(client):
    headers = auth(client, "admin@example.com")
    denied = client.post(
        "/api/v1/admin/courses",
        headers=headers,
        json={"slug": "math-101", "title": "Math 101", "published": True},
    )
    assert denied.status_code == 403
    session = next(app.dependency_overrides[get_session]())
    user = session.exec(select(User).where(User.email == "admin@example.com")).first()
    session.add(UserRole(user_id=user.id, role=RoleName.admin))
    session.commit()
    session.close()
    course = client.post(
        "/api/v1/admin/courses",
        headers=headers,
        json={"slug": "math-101", "title": "Math 101", "published": True},
    )
    assert course.status_code == 201
    module = client.post(
        f"/api/v1/admin/courses/{course.json()['id']}/modules",
        headers=headers,
        json={"title": "Numbers", "position": 0},
    )
    assert module.status_code == 201
    lesson = client.post(
        f"/api/v1/admin/modules/{module.json()['id']}/lessons",
        headers=headers,
        json={
            "title": "Counting",
            "content": "Count to ten",
            "duration_seconds": 40,
            "position": 0,
        },
    )
    assert lesson.status_code == 201
    patched_module = client.patch(
        f"/api/v1/admin/modules/{module.json()['id']}",
        headers=headers,
        json={"title": "Updated Numbers"},
    )
    assert patched_module.status_code == 200
    patched_lesson = client.patch(
        f"/api/v1/admin/lessons/{lesson.json()['id']}",
        headers=headers,
        json={"title": "Counting to Ten"},
    )
    assert patched_lesson.status_code == 200
    assert (
        client.delete(f"/api/v1/admin/lessons/{lesson.json()['id']}", headers=headers).status_code
        == 204
    )
    assert (
        client.delete(f"/api/v1/admin/modules/{module.json()['id']}", headers=headers).status_code
        == 204
    )
    assert client.get("/api/v1/admin/audit-events", headers=headers).status_code == 200
