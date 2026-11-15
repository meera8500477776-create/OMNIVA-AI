from uuid import uuid4


def test_registration_accepts_frontend_name_field(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"name-{uuid4().hex}@example.com",
            "password": "correct-horse-battery-staple",
            "name": "Frontend Learner",
        },
    )

    assert response.status_code == 201
    assert response.json()["user"]["display_name"] == "Frontend Learner"


def test_career_accepts_object_constraints_and_normalizes_to_strings(client):
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"career-{uuid4().hex}@example.com",
            "password": "correct-horse-battery-staple",
            "display_name": "Career Learner",
        },
    )
    assert registered.status_code == 201
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    response = client.post(
        "/api/v1/features/career/recommendations",
        headers=headers,
        json={
            "education_level": "not_specified",
            "interests": ["Creative problem-solving"],
            "skills": [],
            "constraints": {"goal": "Explore accessible learning design"},
            "consent": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["demo"] is True


def test_career_rejects_malformed_object_constraints(client):
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"career-invalid-{uuid4().hex}@example.com",
            "password": "correct-horse-battery-staple",
            "display_name": "Career Learner",
        },
    )
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    response = client.post(
        "/api/v1/features/career/recommendations",
        headers=headers,
        json={
            "education_level": "not_specified",
            "interests": ["design"],
            "constraints": {"goal": ["not", "a", "string"]},
            "consent": True,
        },
    )

    assert response.status_code == 422


def test_profile_patch_auth_me_alias_remains_available(client):
    created = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"profile-{uuid4().hex}@example.com",
            "password": "correct-horse-battery-staple",
            "display_name": "Before Update",
        },
    )
    headers = {"Authorization": f"Bearer {created.json()['access_token']}"}

    response = client.patch(
        "/api/v1/auth/me", headers=headers, json={"display_name": "After Update"}
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "After Update"
