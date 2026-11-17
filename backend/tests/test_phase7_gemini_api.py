import json
from uuid import uuid4

from features.ai_adapters.gemini import GeminiProvider
from features.ai_adapters.gemini_features import GeminiWorkflowPlanner


def _user(client, label):
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": f"phase7-{label}-{uuid4().hex}@example.com",
            "password": "correct-horse-battery-staple",
            "display_name": label,
        },
    )


def _auth(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_gemini_live_mode_wires_tutor_career_voice_care_and_autopilot(client, monkeypatch):
    from app.api.routes import features as feature_routes
    from app.api.routes import phase4_features
    from app.core.config import settings
    from app.main import autopilot_service

    class FakeGemini:
        configured = True

        def __init__(self):
            self.calls = {}

        async def generate(self, *, feature, **kwargs):
            self.calls.setdefault(feature, []).append(kwargs["messages"])
            if feature == "career_guidance":
                return json.dumps(
                    {
                        "recommendations": [
                            {
                                "domain": "Technology",
                                "role": "Data Analyst",
                                "specialization": "Analytics",
                                "match_score": 72,
                                "rationale": ["Matches your interests."],
                                "skill_gaps": ["Statistics"],
                                "roadmap": ["Practice with a small dataset"],
                            }
                        ]
                    }
                )
            if feature == "autopilot_planning":
                return json.dumps(
                    {
                        "steps": [
                            {
                                "id": "review",
                                "description": "Review the request",
                                "tool": "complete",
                                "input": {},
                                "expected_output": "A safe summary",
                                "dependencies": [],
                                "risk": "low",
                                "approval_required": False,
                            }
                        ]
                    }
                )
            return f"Gemini response for {feature}"

    fake = FakeGemini()

    class FakeGnaniVoice:
        configured = True

        async def synthesize(self, text, voice=None, locale="en"):
            return b"RIFF"

    monkeypatch.setattr(feature_routes, "gnani_voice", FakeGnaniVoice())
    monkeypatch.setattr(settings, "app_mode", "real")
    monkeypatch.setattr(feature_routes, "gemini", fake)
    monkeypatch.setattr(phase4_features, "gemini", fake)
    monkeypatch.setattr(autopilot_service, "planner_provider", GeminiWorkflowPlanner(fake))
    owner = _user(client, "owner")
    other = _user(client, "other")
    headers, other_headers = _auth(owner), _auth(other)

    career = client.post(
        "/api/v1/features/career/recommendations",
        headers=headers,
        json={
            "education_level": "college",
            "interests": ["technology"],
            "skills": ["research"],
            "constraints": {"goal": "remote work"},
            "consent": True,
        },
    )
    assert career.status_code == 200 and career.json()["demo"] is False
    assert career.json()["recommendations"][0]["match_score"] == 72

    tutor = client.post(
        "/api/v1/features/tutor/sessions",
        headers=headers,
        json={"consent": True, "topic": "Product design", "duration_minutes": 20},
    )
    assert tutor.status_code == 201 and tutor.json()["demo"] is False
    tutor_turn = client.post(
        f"/api/v1/features/tutor/sessions/{tutor.json()['session_id']}/turns",
        headers=headers,
        json={"text": "Explain contrast"},
    )
    assert (
        tutor_turn.status_code == 200 and "Gemini response for tutor" in tutor_turn.json()["answer"]
    )
    client.post(
        f"/api/v1/features/tutor/sessions/{tutor.json()['session_id']}/turns",
        headers=headers,
        json={"text": "Give me an example"},
    )
    assert any(item["text"] == "Explain contrast" for item in fake.calls["tutor"][1])
    assert (
        client.post(
            f"/api/v1/features/tutor/sessions/{tutor.json()['session_id']}/turns",
            headers=other_headers,
            json={"text": "Read someone else's session"},
        ).status_code
        == 404
    )

    voice = client.post(
        "/api/v1/features/voice/sessions",
        headers=headers,
        json={"consent": True, "mode": "practice", "locale": "en"},
    )
    voice_turn = client.post(
        f"/api/v1/features/voice/sessions/{voice.json()['session_id']}/turns",
        headers=headers,
        json={"text": "Help me practice"},
    )
    assert voice.status_code == 201 and voice.json()["demo"] is False
    assert (
        voice_turn.status_code == 200
        and "Gemini response for voice_assistant" in voice_turn.json()["answer"]
    )
    client.post(
        f"/api/v1/features/voice/sessions/{voice.json()['session_id']}/turns",
        headers=headers,
        json={"text": "Continue the practice"},
    )
    assert any(item["text"] == "Help me practice" for item in fake.calls["voice_assistant"][1])

    care = client.post(
        "/api/v1/features/care-companion/sessions",
        headers=headers,
        json={"persona": "best-friend", "locale": "en", "consent": True},
    )
    care_turn = client.post(
        f"/api/v1/features/care-companion/sessions/{care.json()['session_id']}/turns",
        headers=headers,
        json={"text": "I feel nervous about my presentation"},
    )
    assert care.status_code == 201 and care.json()["demo"] is False
    assert care_turn.status_code == 200 and care_turn.json()["demo"] is False
    client.post(
        f"/api/v1/features/care-companion/sessions/{care.json()['session_id']}/turns",
        headers=headers,
        json={"text": "Can we plan a first step?"},
    )
    assert any(
        item.get("text") == "I feel nervous about my presentation"
        for item in fake.calls["care_companion"][1]
    )

    plan = client.post(
        "/api/v1/autopilot/plans",
        headers=headers,
        json={"request": "Make a safe review plan", "demo": False},
    )
    assert plan.status_code == 200, plan.text
    assert plan.json()["demo"] is False
    assert plan.json()["user_id"] == str(owner.json()["user"]["id"])


def test_live_gemini_features_fail_closed_when_local_key_is_missing(client, monkeypatch):
    from app.api.routes import features as feature_routes
    from app.api.routes import phase4_features
    from app.core.config import settings
    from app.main import autopilot_service

    missing_provider = GeminiProvider(None)
    monkeypatch.setattr(settings, "app_mode", "real")
    monkeypatch.setattr(feature_routes, "gemini", missing_provider)
    monkeypatch.setattr(phase4_features, "gemini", missing_provider)
    monkeypatch.setattr(
        autopilot_service, "planner_provider", GeminiWorkflowPlanner(missing_provider)
    )
    headers = _auth(_user(client, "missing-key"))

    career = client.post(
        "/api/v1/features/career/recommendations",
        headers=headers,
        json={"education_level": "college", "interests": ["technology"], "consent": True},
    )
    tutor = client.post(
        "/api/v1/features/tutor/sessions",
        headers=headers,
        json={"consent": True, "topic": "Mathematics", "duration_minutes": 20},
    )
    voice = client.post(
        "/api/v1/features/voice/sessions",
        headers=headers,
        json={"consent": True, "mode": "practice", "locale": "en"},
    )
    care = client.post(
        "/api/v1/features/care-companion/sessions",
        headers=headers,
        json={"persona": "best-friend", "locale": "en", "consent": True},
    )
    plan = client.post(
        "/api/v1/autopilot/plans",
        headers=headers,
        json={"request": "Plan a safe review", "demo": False},
    )
    assert [response.status_code for response in (career, tutor, voice, care, plan)] == [503] * 5
    assert all(
        "api key" not in response.text.lower() for response in (career, tutor, voice, care, plan)
    )


def test_voice_transcription_is_authenticated_and_accepts_pcm_wav_only(client, monkeypatch):
    import io
    import wave

    from app.api.routes import features as feature_routes
    from app.core.config import settings

    class FakeGemini:
        configured = True

    class FakeGnani:
        configured = True

        async def transcribe_with_metadata(self, audio, locale="en"):
            return {"transcript": "nenu chadutunnanu", "language": "te"}

    monkeypatch.setattr(settings, "app_mode", "real")
    monkeypatch.setattr(feature_routes, "gemini", FakeGemini())
    monkeypatch.setattr(feature_routes, "gnani_voice", FakeGnani())
    owner, other = _user(client, "voice-owner"), _user(client, "voice-other")
    headers, other_headers = _auth(owner), _auth(other)
    created = client.post(
        "/api/v1/features/voice/sessions",
        headers=headers,
        json={"consent": True, "mode": "assistant", "locale": "te"},
    )
    assert created.status_code == 201
    session_id = created.json()["session_id"]
    rejected = client.post(
        f"/api/v1/features/voice/sessions/{session_id}/transcribe",
        headers=headers,
        files={"audio": ("sample.webm", b"webm", "audio/webm")},
    )
    assert rejected.status_code == 415
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 16000)
    response = client.post(
        f"/api/v1/features/voice/sessions/{session_id}/transcribe",
        headers=headers,
        files={"audio": ("sample.wav", audio.getvalue(), "audio/wav")},
    )
    assert response.status_code == 200
    assert response.json() == {"transcript": "nenu chadutunnanu", "language": "te"}
    assert (
        client.post(
            f"/api/v1/features/voice/sessions/{session_id}/transcribe",
            headers=other_headers,
            files={"audio": ("sample.wav", audio.getvalue(), "audio/wav")},
        ).status_code
        == 404
    )
