from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from features.autopilot.router import create_autopilot_router
from features.autopilot.service import AutopilotService


def test_autopilot_router_uses_shared_auth_and_action_approval_contract():
    service = AutopilotService()
    app = FastAPI()

    def current_user(request: Request):
        return SimpleNamespace(id=request.headers.get("X-Test-User", "user-a"))

    app.include_router(create_autopilot_router(service, current_user), prefix="/api/v1")
    client = TestClient(app)
    headers = {"X-Test-User": "user-a"}

    planned = client.post(
        "/api/v1/autopilot/plans",
        json={
            "request": "Find three example AI internships, compare them, draft an application email and schedule a reminder."
        },
        headers=headers,
    )
    assert planned.status_code == 200
    plan_id = planned.json()["id"]
    created = client.post("/api/v1/autopilot/workflows", json={"plan_id": plan_id}, headers=headers)
    workflow_id = created.json()["workflow_id"]
    evidence = client.get(
        f"/api/v1/autopilot/workflows/{workflow_id}/browser-evidence", headers=headers
    )
    assert evidence.status_code == 200
    assert evidence.json()[0]["demo"] is True
    assert client.get(
        f"/api/v1/autopilot/workflows/{workflow_id}/browser-evidence",
        headers={"X-Test-User": "user-b"},
    ).status_code == 403
    assert client.get("/api/v1/autopilot/history", headers=headers).status_code == 200
    assert (
        client.get(
            f"/api/v1/autopilot/workflows/{workflow_id}", headers={"X-Test-User": "user-b"}
        ).status_code
        == 403
    )
    started = client.post(f"/api/v1/autopilot/workflows/{workflow_id}/start", headers=headers)
    assert started.status_code == 200 and started.json()["status"] == "waiting_approval"

    approvals = client.get("/api/v1/autopilot/approvals", headers=headers).json()
    email_approval = next(item for item in approvals if item["step_id"] == "approval-send")
    assert (
        "draft-preview" in email_approval["action_text"]
        or "Exact" not in email_approval["action_text"]
    )
    assert "Hello" in email_approval["action_text"]
    body = {
        "approval_id": email_approval["id"],
        "plan_hash": email_approval["plan_hash"],
        "action_hash": email_approval["action_hash"],
        "confirmed": True,
        "action_text": email_approval["action_text"],
    }
    wrong_action = {**body, "action_text": "send to a different target"}
    assert (
        client.post(
            f"/api/v1/autopilot/approvals/{email_approval['id']}/approve",
            json=wrong_action,
            headers=headers,
        ).status_code
        == 409
    )
    approved = client.post(
        f"/api/v1/autopilot/approvals/{email_approval['id']}/approve", json=body, headers=headers
    )
    assert approved.status_code == 200 and approved.json()["status"] == "waiting_approval"
    denied = next(
        item
        for item in client.get("/api/v1/autopilot/approvals", headers=headers).json()
        if item["step_id"] == "reminder"
    )
    denied_body = {
        "approval_id": denied["id"],
        "plan_hash": denied["plan_hash"],
        "action_hash": denied["action_hash"],
        "confirmed": False,
        "action_text": denied["action_text"],
    }
    finished = client.post(
        f"/api/v1/autopilot/approvals/{denied['id']}/deny", json=denied_body, headers=headers
    )
    assert finished.status_code == 200 and finished.json()["status"] == "partial"
    assert finished.json()["steps"][3]["result"]["sent"] is False


def test_memory_api_requires_opt_in_and_scopes_records_to_authenticated_user():
    service = AutopilotService()
    app = FastAPI()

    def current_user(request: Request):
        return SimpleNamespace(id=request.headers.get("X-Test-User", "user-a"))

    app.include_router(create_autopilot_router(service, current_user), prefix="/api/v1")
    client = TestClient(app)
    memory = {"content": "Enjoys robotics", "provenance": "user-provided", "retention_days": 5}
    assert client.post("/api/v1/autopilot/memory", json=memory).status_code == 403
    assert (
        client.post("/api/v1/autopilot/memory/consent", json={"consented": True}).status_code == 200
    )
    created = client.post("/api/v1/autopilot/memory", json=memory)
    assert created.status_code == 200
    memory_id = created.json()["id"]
    assert client.get("/api/v1/autopilot/memory").json()[0]["id"] == memory_id
    assert (
        client.get("/api/v1/autopilot/memory", headers={"X-Test-User": "user-b"}).status_code == 403
    )
    assert client.delete(f"/api/v1/autopilot/memory/{memory_id}").status_code == 204
    assert client.get("/api/v1/autopilot/memory").json() == []
