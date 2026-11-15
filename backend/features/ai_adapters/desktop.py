"""Safe desktop intent preview boundary. No OS automation is implemented here."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field

from .common import AdapterError, Mode, RuntimeConfig, new_id, run_bounded, utc_now


@dataclass(slots=True)
class DesktopSession:
    session_id: str
    user_id: str
    capabilities: tuple[str, ...]
    consent_version: str
    state: str = "ready"
    pending_plan_hash: str | None = None
    approved_plan_hash: str | None = None
    execution_id: str | None = None
    cancellation_requested: bool = False
    in_flight: asyncio.Task[object] | None = None
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class DesktopPlan:
    plan_id: str
    session_id: str
    action: str
    display_text: str
    impact: str
    plan_hash: str
    approval_required: bool = True
    simulation: bool = True


class DesktopAdapter:
    """Only interprets two exact safe intents. Real execution requires an injected companion."""

    def __init__(
        self,
        config: RuntimeConfig | None = None,
        executor: Callable[[DesktopPlan], Awaitable[dict[str, object]]] | None = None,
    ) -> None:
        self.config = config or RuntimeConfig()
        self.executor = executor
        self.sessions: dict[str, DesktopSession] = {}
        self.plans: dict[str, DesktopPlan] = {}

    def create_session(
        self,
        user_id: str,
        capabilities: list[str],
        consent_version: str,
        user_initiated: bool,
        mode: Mode | None = None,
    ) -> dict[str, object]:
        if not user_initiated:
            raise AdapterError(
                "user_action_required", "Start the desktop session from the local companion", 403
            )
        if not consent_version.strip():
            raise AdapterError("consent_required", "A consent version is required", 403)
        allowed = {"preview"}
        if self.config.real_desktop_approved and self.executor is not None:
            allowed.add("execute")
        requested = set(capabilities)
        if requested - allowed:
            raise AdapterError(
                "capability_not_allowed", "Only the preview capability is available", 403
            )
        session = DesktopSession(new_id(), user_id, tuple(sorted(requested)), consent_version)
        self.sessions[session.session_id] = session
        return {
            "session_id": session.session_id,
            "companion_challenge": new_id(),
            "state": session.state,
            "mode": (mode or self.config.default_mode).value,
        }

    def preview(self, session_id: str, command: str) -> dict[str, object]:
        session = self._session(session_id)
        if session.state != "ready":
            raise AdapterError("session_state_conflict", "Desktop session is not ready", 409)
        normalized = " ".join(command.casefold().split())
        # No free-form command execution, URLs, paths, shell or generated argument payloads.
        if normalized not in {"open calculator", "launch calculator"}:
            raise AdapterError(
                "command_not_allowed", "This desktop command is not in the preview allowlist", 422
            )
        action = "open_calculator"
        material = json.dumps({"session": session_id, "action": action}, sort_keys=True).encode()
        digest = hashlib.sha256(material).hexdigest()
        plan = DesktopPlan(new_id(), session_id, action, "Open Calculator", "low", digest)
        self.plans[plan.plan_id] = plan
        session.pending_plan_hash = digest
        session.state = "awaiting_approval"
        return {
            "plan_id": plan.plan_id,
            "plan_hash": digest,
            "actions": [asdict(plan)],
            "approval_required": True,
            "simulation": True,
        }

    def approve(
        self, session_id: str, plan_id: str, plan_hash: str, confirmed: bool
    ) -> dict[str, object]:
        session = self._session(session_id)
        plan = self._plan(session_id, plan_id)
        if session.state != "awaiting_approval":
            raise AdapterError(
                "session_state_conflict", "Desktop session is not awaiting approval", 409
            )
        if not confirmed:
            raise AdapterError(
                "explicit_confirmation_required",
                "Confirm this exact plan in the local companion",
                403,
            )
        if not plan_hash or plan_hash != plan.plan_hash or session.pending_plan_hash != plan_hash:
            raise AdapterError(
                "plan_hash_mismatch", "The approved plan changed; preview it again", 409
            )
        session.approved_plan_hash = plan_hash
        session.state = "approved"
        return {"session_id": session_id, "plan_id": plan_id, "state": "approved"}

    async def execute(
        self, session_id: str, plan_id: str, mode: Mode | None = None
    ) -> dict[str, object]:
        session = self._session(session_id)
        plan = self._plan(session_id, plan_id)
        selected_mode = mode or self.config.default_mode
        if session.cancellation_requested:
            raise AdapterError("execution_cancelled", "Desktop execution was cancelled", 409)
        if session.state != "approved" or session.approved_plan_hash != plan.plan_hash:
            raise AdapterError("approval_required", "Approve the exact plan before execution", 403)
        if selected_mode == Mode.DEMO:
            session.execution_id = new_id()
            session.state = "completed"
            return {
                "execution_id": session.execution_id,
                "state": "completed",
                "simulation": True,
                "message": "Simulated desktop action; the operating system was not controlled",
            }
        # This adapter intentionally has no OS executor. Configuration alone is insufficient.
        if not self.config.real_desktop_approved or self.executor is None:
            raise AdapterError(
                "desktop_executor_unavailable",
                "Real desktop execution requires an approved local companion",
                503,
            )
        if "execute" not in session.capabilities:
            raise AdapterError(
                "capability_not_approved", "This session lacks local execute capability", 403
            )
        session.execution_id = new_id()
        session.state = "running"
        task = asyncio.current_task()
        session.in_flight = task
        try:
            result = await run_bounded(
                self.executor(plan), self.config.provider_timeout_seconds, "desktop"
            )
        except asyncio.CancelledError:
            session.state = "cancelled"
            raise
        except Exception:
            session.state = "failed"
            raise
        finally:
            if session.in_flight is task:
                session.in_flight = None
        if session.cancellation_requested:
            session.state = "cancelled"
            raise AdapterError("execution_cancelled", "Desktop execution was cancelled", 409)
        session.state = "completed"
        return {
            "execution_id": session.execution_id,
            "state": "completed",
            "simulation": False,
            "result": result,
        }

    def cancel(self, session_id: str) -> dict[str, object]:
        session = self._session(session_id)
        if session.state in {"completed", "failed"}:
            return {"session_id": session_id, "state": session.state, "emergency_stop": False}
        session.cancellation_requested = True
        if session.in_flight is not None and session.in_flight is not asyncio.current_task():
            session.in_flight.cancel()
        session.state = "cancelled"
        return {"session_id": session_id, "state": session.state, "emergency_stop": True}

    def status(self, session_id: str) -> dict[str, object]:
        session = self._session(session_id)
        return {
            "session_id": session_id,
            "state": session.state,
            "execution_id": session.execution_id,
            "cancellation_requested": session.cancellation_requested,
        }

    def _session(self, session_id: str) -> DesktopSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise AdapterError("session_not_found", "Desktop session was not found", 404)
        return session

    def _plan(self, session_id: str, plan_id: str) -> DesktopPlan:
        plan = self.plans.get(plan_id)
        if plan is None or plan.session_id != session_id:
            raise AdapterError("plan_not_found", "Desktop plan was not found", 404)
        return plan
