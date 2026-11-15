from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolType(StrEnum):
    SEARCH = "search"
    CAREER = "career"
    EMAIL_DRAFT = "email_draft"
    EMAIL_SEND = "email_send"
    REMINDER = "reminder"
    BROWSER_READ = "browser_read"
    BROWSER_FILL = "browser_fill"
    DESKTOP = "desktop"
    TUTOR = "tutor"
    VOICE = "voice"
    COMPANION = "companion"
    AVATAR = "avatar"
    NOTIFY = "notify"
    CONDITION = "condition"
    DELAY = "delay"
    COMPLETE = "complete"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class WorkflowStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeType(StrEnum):
    TRIGGER = "trigger"
    CONDITION = "condition"
    TOOL = "tool"
    APPROVAL = "approval"
    DELAY = "delay"
    NOTIFICATION = "notification"
    COMPLETION = "completion"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RetryPolicy(StrictModel):
    max_retries: int = Field(default=0, ge=0, le=2)
    backoff_seconds: float = Field(default=0.05, ge=0, le=5)


class WorkflowStep(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    description: str = Field(min_length=1, max_length=240)
    tool: ToolType
    input: dict[str, Any] = Field(default_factory=dict)
    expected_output: str = Field(min_length=1, max_length=240)
    dependencies: list[str] = Field(default_factory=list, max_length=30)
    risk: Risk
    approval_required: bool = False
    timeout_seconds: float = Field(default=10, gt=0, le=120)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    parallel_safe: bool = False
    status: StepStatus = StepStatus.PENDING
    result: dict[str, Any] | None = None
    error_code: str | None = None
    attempts: int = 0
    approval_id: str | None = None

    @field_validator("input")
    @classmethod
    def limit_input_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        import json

        if len(json.dumps(value, default=str).encode("utf-8")) > 10_000:
            raise ValueError("Step input exceeds 10 KB")
        return value


class WorkflowPlan(StrictModel):
    id: str
    user_id: str
    request: str = Field(min_length=1, max_length=2000)
    demo: bool = True
    steps: list[WorkflowStep] = Field(min_length=1, max_length=30)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_steps(self):
        ids = [s.id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Step IDs must be unique")
        known = set(ids)
        for s in self.steps:
            if s.id in s.dependencies:
                raise ValueError("A step cannot depend on itself")
            missing = set(s.dependencies) - known
            if missing:
                raise ValueError(f"Missing dependencies for {s.id}: {sorted(missing)}")
            if s.risk == Risk.HIGH and not s.approval_required:
                raise ValueError("High-risk steps require approval")
        graph = {s.id: set(s.dependencies) for s in self.steps}
        seen = set()
        active = set()

        def visit(node):
            if node in active:
                raise ValueError("Workflow dependencies contain a cycle")
            if node in seen:
                return
            active.add(node)
            for dep in graph[node]:
                visit(dep)
            active.remove(node)
            seen.add(node)

        for node in ids:
            visit(node)
        return self

    def integrity_hash(self) -> str:
        import hashlib
        import json

        immutable = [
            {
                k: getattr(step, k)
                for k in (
                    "id",
                    "description",
                    "tool",
                    "input",
                    "expected_output",
                    "dependencies",
                    "risk",
                    "approval_required",
                    "timeout_seconds",
                    "retry_policy",
                    "parallel_safe",
                )
            }
            for step in self.steps
        ]
        stable = {
            "id": self.id,
            "user_id": self.user_id,
            "request": self.request,
            "demo": self.demo,
            "steps": immutable,
        }
        encoded = json.dumps(
            stable,
            sort_keys=True,
            default=lambda value: value.value if isinstance(value, StrEnum) else value.model_dump(),
            separators=(",", ":"),
        )
        return hashlib.sha256(encoded.encode()).hexdigest()


class PlanRequest(StrictModel):
    request: str = Field(min_length=3, max_length=2000)
    demo: bool = True


class WorkflowCreate(StrictModel):
    plan_id: str = Field(min_length=1, max_length=80)


class MemoryConsentRequest(StrictModel):
    consented: bool


class EmergencyStopRequest(StrictModel):
    confirmed: bool


class WorkflowPlanResponse(StrictModel):
    plan: WorkflowPlan
    plan_hash: str


class ApprovalRequest(StrictModel):
    approval_id: str
    plan_hash: str = Field(min_length=64, max_length=64)
    action_hash: str = Field(min_length=64, max_length=64)
    confirmed: bool
    action_text: str = Field(min_length=1, max_length=5000)


class WorkflowEvent(StrictModel):
    workflow_id: str
    sequence: int
    type: str
    step_id: str | None = None
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any] = Field(default_factory=dict)


class MemoryInput(StrictModel):
    content: str = Field(min_length=1, max_length=1000)
    provenance: str = Field(min_length=1, max_length=120)
    retention_days: int = Field(default=30, ge=1, le=365)


class MemoryRecord(StrictModel):
    id: str
    user_id: str
    content: str
    provenance: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class WorkflowNode(StrictModel):
    id: str
    type: NodeType
    label: str
    step_id: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinition(StrictModel):
    id: str
    nodes: list[WorkflowNode] = Field(min_length=1, max_length=60)
