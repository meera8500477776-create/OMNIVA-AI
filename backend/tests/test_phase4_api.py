from uuid import uuid4


def create_user(client, name="Feature User"):
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": f"feature-{uuid4().hex}@example.com",
            "password": "correct-horse-battery-staple",
            "display_name": name,
        },
    )


def auth(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_email_demo_draft_explicit_approval_send_and_idempotency(client):
    user = create_user(client)
    headers = auth(user)

    inbox = client.get("/api/v1/features/email-agent/inbox", headers=headers)
    assert inbox.status_code == 200
    assert inbox.json()["demo"] is True
    assert "fictional" in inbox.json()["label"].lower()
    email_id = inbox.json()["items"][0]["email"]["id"]

    draft = client.post(
        "/api/v1/features/email-agent/drafts",
        headers=headers,
        json={"email_id": email_id, "tone": "professional"},
    )
    assert draft.status_code == 200 and draft.json()["demo"] is True
    draft_id = draft.json()["draft_id"]

    without_approval = client.post(
        "/api/v1/features/email-agent/send",
        headers={**headers, "Idempotency-Key": "qa-no-approval-001"},
        json={"approval": "missing"},
    )
    assert without_approval.status_code == 403

    approval = client.post(
        "/api/v1/features/email-agent/approvals",
        headers=headers,
        json={"draft_id": draft_id},
    )
    result = client.post(
        "/api/v1/features/email-agent/send",
        headers={**headers, "Idempotency-Key": "qa-email-send-001"},
        json={"approval": approval.json()["approval"]},
    )
    assert result.status_code == 200
    assert result.json()["sent"] is False and result.json()["demo"] is True

    second_approval = client.post(
        "/api/v1/features/email-agent/approvals",
        headers=headers,
        json={"draft_id": draft_id},
    )
    duplicate = client.post(
        "/api/v1/features/email-agent/send",
        headers={**headers, "Idempotency-Key": "qa-email-send-001"},
        json={"approval": second_approval.json()["approval"]},
    )
    assert duplicate.status_code == 409


def test_email_approval_is_user_bound_and_emergency_disable_blocks_send(client):
    owner = create_user(client)
    other = create_user(client)
    owner_headers = auth(owner)
    other_headers = auth(other)
    draft = client.post(
        "/api/v1/features/email-agent/drafts",
        headers=owner_headers,
        json={"email_id": "demo-001"},
    )
    approval = client.post(
        "/api/v1/features/email-agent/approvals",
        headers=owner_headers,
        json={"draft_id": draft.json()["draft_id"]},
    )
    wrong_owner = client.post(
        "/api/v1/features/email-agent/send",
        headers={**other_headers, "Idempotency-Key": "qa-other-owner-001"},
        json={"approval": approval.json()["approval"]},
    )
    assert wrong_owner.status_code == 403

    disabled = client.post("/api/v1/features/email-agent/emergency-disable", headers=owner_headers)
    blocked = client.post(
        "/api/v1/features/email-agent/send",
        headers={**owner_headers, "Idempotency-Key": "qa-disabled-send-001"},
        json={"approval": approval.json()["approval"]},
    )
    assert disabled.status_code == 200
    assert blocked.status_code == 503


def test_care_companion_consent_personas_memory_and_owner_isolation(client):
    owner = create_user(client)
    other = create_user(client)
    owner_headers = auth(owner)
    other_headers = auth(other)

    personas = client.get("/api/v1/features/care-companion/personas", headers=owner_headers)
    assert personas.status_code == 200 and len(personas.json()["items"]) == 6
    denied = client.post(
        "/api/v1/features/care-companion/sessions",
        headers=owner_headers,
        json={"persona": "best-friend", "consent": False},
    )
    assert denied.status_code == 403

    started = client.post(
        "/api/v1/features/care-companion/sessions",
        headers=owner_headers,
        json={"persona": "best-friend", "locale": "en", "consent": True},
    )
    assert started.status_code == 201 and started.json()["ai_identity"] is True
    session_id = started.json()["session_id"]
    turn = client.post(
        f"/api/v1/features/care-companion/sessions/{session_id}/turns",
        headers=owner_headers,
        json={"text": "I had a difficult day."},
    )
    assert turn.status_code == 200 and turn.json()["demo"] is True
    assert "[DEMO" in turn.json()["answer"]
    assert (
        client.get(
            f"/api/v1/features/care-companion/sessions/{session_id}", headers=other_headers
        ).status_code
        == 404
    )

    no_consent = client.post(
        "/api/v1/features/care-companion/memory",
        headers=owner_headers,
        json={"content": "likes gardening"},
    )
    assert no_consent.status_code == 403
    enabled = client.put(
        "/api/v1/features/care-companion/memory/consent",
        headers=owner_headers,
        json={"consent": True},
    )
    saved = client.post(
        "/api/v1/features/care-companion/memory",
        headers=owner_headers,
        json={"content": "likes gardening"},
    )
    assert enabled.json()["enabled"] is True
    assert saved.json()["items"] == ["likes gardening"]
    assert (
        client.delete("/api/v1/features/care-companion/memory", headers=owner_headers).status_code
        == 204
    )


def test_care_deadline_reminder_consent_persistence_idempotency_and_owner_scope(client):
    owner = create_user(client)
    other = create_user(client)
    headers = auth(owner)
    other_headers = auth(other)
    payload = {
        "title": "Submit project",
        "body": "Review the final draft",
        "reminder_type": "deadline",
        "scheduled_at": "2030-05-01T12:00:00+05:30",
        "timezone_name": "Asia/Kolkata",
        "quiet_start": "22:00",
        "quiet_end": "08:00",
        "consent": False,
    }
    denied = client.post(
        "/api/v1/features/care-companion/reminders",
        headers={**headers, "Idempotency-Key": "reminder-consent-001"},
        json=payload,
    )
    assert denied.status_code == 403

    payload["consent"] = True
    created = client.post(
        "/api/v1/features/care-companion/reminders",
        headers={**headers, "Idempotency-Key": "reminder-submit-001"},
        json=payload,
    )
    assert created.status_code == 201
    reminder_id = created.json()["id"]
    repeated = client.post(
        "/api/v1/features/care-companion/reminders",
        headers={**headers, "Idempotency-Key": "reminder-submit-001"},
        json=payload,
    )
    assert repeated.status_code == 201 and repeated.json()["id"] == reminder_id
    conflict_payload = {**payload, "title": "Changed title"}
    conflict = client.post(
        "/api/v1/features/care-companion/reminders",
        headers={**headers, "Idempotency-Key": "reminder-submit-001"},
        json=conflict_payload,
    )
    assert conflict.status_code == 409
    assert client.get("/api/v1/features/care-companion/reminders", headers=headers).json()["items"]
    assert (
        client.get("/api/v1/features/care-companion/reminders", headers=other_headers).json()[
            "items"
        ]
        == []
    )
    assert (
        client.post(
            f"/api/v1/features/care-companion/reminders/{reminder_id}/acknowledge",
            headers=other_headers,
        ).status_code
        == 404
    )


def test_autopilot_internship_workflow_stops_at_approval_and_is_user_bound(client):
    owner = create_user(client)
    other = create_user(client)
    owner_headers = auth(owner)

    anonymous = client.post(
        "/api/v1/autopilot/plans", json={"request": "Help me find internships", "demo": True}
    )
    assert anonymous.status_code == 401

    planned = client.post(
        "/api/v1/autopilot/plans",
        headers=owner_headers,
        json={"request": "Help me find internships", "demo": True},
    )
    assert planned.status_code == 200
    plan = planned.json()
    assert plan["demo"] is True
    assert any(step["approval_required"] for step in plan["steps"])

    created = client.post(
        "/api/v1/autopilot/workflows",
        headers=owner_headers,
        json={"plan_id": plan["id"]},
    )
    workflow_id = created.json()["workflow_id"]
    started = client.post(f"/api/v1/autopilot/workflows/{workflow_id}/start", headers=owner_headers)
    assert started.status_code == 200
    assert started.json()["demo"] is True
    assert started.json()["status"] == "waiting_approval"
    assert any(step["status"] == "waiting_approval" for step in started.json()["steps"])
    assert (
        client.get(f"/api/v1/autopilot/workflows/{workflow_id}", headers=auth(other)).status_code
        == 403
    )

    snapshot = started.json()
    for _ in range(2):
        pending = client.get("/api/v1/autopilot/approvals", headers=owner_headers).json()
        approval = next(item for item in pending if item["status"] == "pending")
        decision = client.post(
            f"/api/v1/autopilot/approvals/{approval['id']}/approve",
            headers=owner_headers,
            json={
                "approval_id": approval["id"],
                "plan_hash": approval["plan_hash"],
                "action_hash": approval["action_hash"],
                "confirmed": True,
                "action_text": approval["action_text"],
            },
        )
        assert decision.status_code == 200
        snapshot = decision.json()

    assert snapshot["status"] == "completed"
    assert all(step["status"] == "succeeded" for step in snapshot["steps"])
    assert any("simulated" in str(step["result"]).lower() for step in snapshot["steps"])


def test_demo_adapters_fail_closed_when_application_is_live(client, monkeypatch):
    from app.core.config import settings

    user = create_user(client)
    headers = auth(user)
    monkeypatch.setattr(settings, "app_mode", "real")

    email = client.get("/api/v1/features/email-agent/inbox", headers=headers)
    care = client.get("/api/v1/features/care-companion/personas", headers=headers)
    autopilot = client.post(
        "/api/v1/autopilot/plans",
        headers=headers,
        json={"request": "Help me find internships", "demo": True},
    )

    assert email.status_code == care.status_code == autopilot.status_code == 503
