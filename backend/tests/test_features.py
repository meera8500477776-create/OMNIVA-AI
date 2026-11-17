def auth(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "features@example.com",
            "password": "correct-horse-battery-staple",
            "display_name": "Learner",
        },
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_demo_features_are_explicit_and_no_action(client):
    headers = auth(client)
    career = client.post(
        "/api/v1/features/career/recommendations",
        headers=headers,
        json={
            "education_level": "undergraduate",
            "interests": ["design"],
            "skills": [],
            "consent": True,
        },
    )
    assert career.status_code == 200 and career.json()["demo"] is True
    assert "limitations" in career.json()
    voice = client.post(
        "/api/v1/features/voice/sessions",
        headers=headers,
        json={"mode": "practice", "locale": "en", "consent": True},
    )
    assert voice.status_code == 201 and voice.json()["demo"] is True
    assert voice.json()["state"] == "simulated" and voice.json()["token"] is None
    desktop = client.post(
        "/api/v1/features/desktop/sessions",
        headers=headers,
        json={"capabilities": ["open_course"], "consent_version": "v1"},
    )
    assert desktop.status_code == 201 and desktop.json()["state"] == "simulated"
    assert desktop.json()["companion_challenge"] is None


def test_invalid_feature_inputs_and_consent(client):
    headers = auth(client)
    assert (
        client.post(
            "/api/v1/features/voice/sessions",
            headers=headers,
            json={"mode": "practice", "locale": "en"},
        ).status_code
        == 403
    )
    result = client.post(
        "/api/v1/features/desktop/sessions",
        headers=headers,
        json={"capabilities": ["run_shell"], "consent_version": "v1"},
    )
    assert result.status_code == 422
    assert (
        client.post(
            "/api/v1/features/career/recommendations",
            headers=headers,
            json={"education_level": "college", "interests": ["art"], "consent": False},
        ).status_code
        == 403
    )


def test_real_mode_never_silently_uses_demo(client, monkeypatch):
    from app.api.routes import features
    from app.core.config import settings

    monkeypatch.setattr(settings, "app_mode", "real")
    monkeypatch.setattr(features.gemini, "_api_key", None)
    response = client.post(
        "/api/v1/features/voice/sessions",
        headers=auth(client),
        json={"mode": "practice", "locale": "en", "consent": True},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"


def test_live_career_normalizes_gemini_top_level_recommendation_array(client, monkeypatch):

    from app.api.routes import features
    from app.core.config import settings

    async def generate(**_kwargs):
        return '[{"domain":"Design","role":"Accessibility designer","specialization":"Inclusive products","match_score":72,"rationale":"Builds on design interests","skill_gaps":["Accessibility testing"],"roadmap":["Study WCAG basics","Audit a page","Share findings"]}]'

    monkeypatch.setattr(settings, "app_mode", "real")
    monkeypatch.setattr(features.gemini, "_api_key", "unit-test-key")
    monkeypatch.setattr(features.gemini, "generate", generate)
    response = client.post(
        "/api/v1/features/career/recommendations",
        headers=auth(client),
        json={
            "education_level": "not_specified",
            "interests": ["design"],
            "skills": [],
            "constraints": {"goal": "Explore accessible design"},
            "consent": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["demo"] is False
    assert response.json()["recommendations"][0]["role"] == "Accessibility designer"
    assert response.json()["recommendations"][0]["rationale"] == ["Builds on design interests"]
