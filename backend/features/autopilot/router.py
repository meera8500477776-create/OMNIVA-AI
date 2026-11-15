from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .contracts import (
    ApprovalRequest,
    EmergencyStopRequest,
    MemoryConsentRequest,
    MemoryInput,
    PlanRequest,
    WorkflowCreate,
)
from .exceptions import AutopilotError
from .service import AutopilotService


def _user_id(user: Any) -> str:
    value = getattr(user, "id", None)
    if value is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "authentication_required", "message": "Authentication required"},
        )
    return str(value)


def _http_error(exc: AutopilotError):
    return HTTPException(
        status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}
    )


def _snapshot(run):
    return {
        "workflow_id": run.id,
        "plan": run.plan,
        "plan_hash": run.plan_hash,
        "status": run.status,
        "events": run.events,
        "demo": run.plan.demo,
        "steps": run.plan.steps,
    }


def create_autopilot_router(
    service: AutopilotService, current_user_dependency: Callable[..., Any]
) -> APIRouter:
    """Router factory mounted by the existing app; caller supplies shared auth dependency."""
    router = APIRouter(prefix="/autopilot", tags=["autopilot"])

    @router.post("/plans")
    async def create_plan(payload: PlanRequest, user=Depends(current_user_dependency)):
        try:
            return await service.create_plan(payload, _user_id(user))
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.get("/plans/{plan_id}")
    def get_plan(plan_id: str, user=Depends(current_user_dependency)):
        try:
            return service.get_plan(plan_id, _user_id(user))
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.post("/workflows")
    def create_workflow(payload: WorkflowCreate, user=Depends(current_user_dependency)):
        try:
            run = service.create_workflow(payload.plan_id, _user_id(user))
            return _snapshot(run)
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.get("/workflows/{workflow_id}")
    def get_workflow(workflow_id: str, user=Depends(current_user_dependency)):
        try:
            return _snapshot(service.workflow(workflow_id, _user_id(user)))
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.post("/workflows/{workflow_id}/start")
    async def start_workflow(workflow_id: str, user=Depends(current_user_dependency)):
        try:
            return _snapshot(await service.orchestrator.start(workflow_id, _user_id(user)))
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.post("/workflows/{workflow_id}/pause")
    def pause_workflow(workflow_id: str, user=Depends(current_user_dependency)):
        try:
            return _snapshot(service.orchestrator.pause(workflow_id, _user_id(user)))
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.post("/workflows/{workflow_id}/resume")
    async def resume_workflow(workflow_id: str, user=Depends(current_user_dependency)):
        try:
            service.orchestrator.resume(workflow_id, _user_id(user))
            return _snapshot(await service.orchestrator.start(workflow_id, _user_id(user)))
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.post("/workflows/{workflow_id}/cancel")
    def cancel_workflow(workflow_id: str, user=Depends(current_user_dependency)):
        try:
            return _snapshot(service.orchestrator.cancel(workflow_id, _user_id(user)))
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.get("/workflows/{workflow_id}/events")
    def workflow_events(workflow_id: str, user=Depends(current_user_dependency)):
        try:
            return service.orchestrator.events(workflow_id, _user_id(user))
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.get("/approvals")
    def approvals(user=Depends(current_user_dependency)):
        return service.approvals_for_user(_user_id(user))

    @router.post("/approvals/{approval_id}/approve")
    async def approve(
        approval_id: str, payload: ApprovalRequest, user=Depends(current_user_dependency)
    ):
        try:
            if not payload.confirmed:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "confirmation_required",
                        "message": "Approval must explicitly confirm the displayed action",
                    },
                )
            item = service.orchestrator.resolve_approval(
                approval_id,
                _user_id(user),
                plan_hash=payload.plan_hash,
                action_hash=payload.action_hash,
                confirmed=True,
                action_text=payload.action_text,
            )
            run = service.workflow(item.workflow_id, _user_id(user))
            return _snapshot(await service.orchestrator.start(run.id, _user_id(user)))
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.post("/approvals/{approval_id}/deny")
    async def deny(
        approval_id: str, payload: ApprovalRequest, user=Depends(current_user_dependency)
    ):
        if payload.confirmed:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_denial", "message": "Denial must not confirm the action"},
            )
        try:
            item = service.orchestrator.resolve_approval(
                approval_id,
                _user_id(user),
                plan_hash=payload.plan_hash,
                action_hash=payload.action_hash,
                confirmed=False,
                action_text=payload.action_text,
            )
            return _snapshot(await service.orchestrator.start(item.workflow_id, _user_id(user)))
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.post("/emergency-stop")
    def emergency_stop(user=Depends(current_user_dependency)):
        service.orchestrator.emergency_stop(_user_id(user))
        return {"stopped": True, "message": "No new Autopilot actions will start."}

    @router.post("/emergency-stop/release")
    def release_emergency_stop(
        payload: EmergencyStopRequest, user=Depends(current_user_dependency)
    ):
        try:
            service.orchestrator.release_emergency_stop(_user_id(user), payload.confirmed)
            return {
                "stopped": False,
                "message": "Emergency stop released after explicit confirmation.",
            }
        except AutopilotError as exc:
            raise _http_error(exc) from exc @ router.get("/history")

    def history(user=Depends(current_user_dependency)):
        return [_snapshot(run) for run in service.history(_user_id(user))]

    @router.post("/memory/consent")
    def memory_consent(payload: MemoryConsentRequest, user=Depends(current_user_dependency)):
        try:
            service.memory.enable(
                _user_id(user), payload.consented
            ) if payload.consented else service.memory.disable(_user_id(user))
            return {"enabled": payload.consented}
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.get("/memory")
    def memories(query: str = "", user=Depends(current_user_dependency)):
        try:
            return service.memory.retrieve(_user_id(user), query)
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.post("/memory")
    def add_memory(payload: MemoryInput, user=Depends(current_user_dependency)):
        try:
            return service.memory.add(_user_id(user), payload)
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.put("/memory/{memory_id}")
    def update_memory(memory_id: str, payload: MemoryInput, user=Depends(current_user_dependency)):
        try:
            return service.memory.update(_user_id(user), memory_id, payload)
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.delete("/memory/{memory_id}", status_code=204)
    def delete_memory(memory_id: str, user=Depends(current_user_dependency)):
        try:
            service.memory.delete(_user_id(user), memory_id)
            return None
        except AutopilotError as exc:
            raise _http_error(exc) from exc

    @router.delete("/memory", status_code=204)
    def delete_all_memory(user=Depends(current_user_dependency)):
        service.memory.delete_all(_user_id(user))
        return None

    return router
