from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from .contracts import WorkflowEvent, WorkflowPlan, WorkflowStatus
from .exceptions import Forbidden, NotFound


@dataclass
class WorkflowRun:
    plan: WorkflowPlan
    owner_id: str
    plan_hash: str
    status: WorkflowStatus = WorkflowStatus.DRAFT
    events: list[WorkflowEvent] = field(default_factory=list)
    pause_requested: bool = False
    cancel_requested: bool = False
    idempotency_results: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def id(self):
        return self.plan.id


class WorkflowRepository(Protocol):
    def create(self, run: WorkflowRun) -> None: ...
    def get(self, workflow_id: str, user_id: str) -> WorkflowRun: ...
    def save(self, run: WorkflowRun) -> None: ...
    def list(self, user_id: str) -> list[WorkflowRun]: ...


class InMemoryWorkflowRepository:
    """Test/demo repository. Phase 6 replaces it with a transaction-backed PostgreSQL implementation."""

    def __init__(self):
        self.items: dict[str, WorkflowRun] = {}

    def create(self, run):
        if run.id in self.items:
            raise ValueError("Workflow already exists")
        self.items[run.id] = run

    def get(self, workflow_id, user_id):
        run = self.items.get(workflow_id)
        if run is None:
            raise NotFound("Workflow was not found")
        if run.owner_id != user_id:
            raise Forbidden("Workflow belongs to another user")
        return run

    def save(self, run):
        self.items[run.id] = run

    def list(self, user_id):
        return [r for r in self.items.values() if r.owner_id == user_id]


def event(run: WorkflowRun, event_type: str, message: str, step_id: str | None = None, **data):
    item = WorkflowEvent(
        workflow_id=run.id,
        sequence=len(run.events) + 1,
        type=event_type,
        step_id=step_id,
        message=message,
        timestamp=datetime.now(UTC),
        data=data,
    )
    run.events.append(item)
    return item
