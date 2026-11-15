from datetime import UTC, datetime, timedelta

from sqlmodel import select

from app.api.deps import get_session
from app.core.security import new_opaque_token, token_digest
from app.db.models import PasswordReset, User
from app.main import app


def register(client, email="student@example.com"):
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "display_name": "Test Student",
        },
    )


def bearer(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_register_login_me_and_logout(client):
    created = register(client)
    assert created.status_code == 201
    assert created.json()["user"]["roles"] == ["student"]
    assert "password_hash" not in created.json()["user"]
    assert "omniva_refresh=" in created.headers["set-cookie"]
    assert client.get("/api/v1/auth/me", headers=bearer(created)).status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "STUDENT@example.com", "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 200
    logout = client.post("/api/v1/auth/logout", headers=bearer(login), cookies=login.cookies)
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me", headers=bearer(login)).status_code == 401


def test_duplicate_and_invalid_login(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "student@example.com", "password": "wrong-password"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "missing@example.com", "password": "wrong-password"},
        ).status_code
        == 401
    )


def test_refresh_rotates_one_time_session(client):
    first = register(client)
    first_cookie = client.cookies.get("omniva_refresh")
    response = client.post("/api/v1/auth/refresh", cookies={"omniva_refresh": first_cookie})
    assert response.status_code == 200
    assert response.json()["access_token"] != first.json()["access_token"]
    assert (
        client.post("/api/v1/auth/refresh", cookies={"omniva_refresh": first_cookie}).status_code
        == 401
    )


def test_password_reset_single_use_and_revokes_sessions(client):
    created = register(client)
    session = next(app.dependency_overrides[get_session]())
    user = session.exec(select(User).where(User.email == "student@example.com")).first()
    raw = new_opaque_token()
    session.add(
        PasswordReset(
            user_id=user.id,
            token_hash=token_digest(raw),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
    )
    session.commit()
    session.close()
    reset = client.post(
        "/api/v1/auth/password/reset",
        json={"token": raw, "new_password": "a-new-secure-password-123"},
    )
    assert reset.status_code == 204
    assert (
        client.post(
            "/api/v1/auth/password/reset",
            json={"token": raw, "new_password": "another-new-password-123"},
        ).status_code
        == 400
    )
    assert client.get("/api/v1/auth/me", headers=bearer(created)).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "student@example.com", "password": "a-new-secure-password-123"},
        ).status_code
        == 200
    )


def test_forgot_password_is_enumeration_safe(client):
    one = client.post("/api/v1/auth/password/forgot", json={"email": "unknown@example.com"})
    register(client)
    two = client.post("/api/v1/auth/password/forgot", json={"email": "student@example.com"})
    assert one.status_code == two.status_code == 202
    assert one.json() == two.json()
