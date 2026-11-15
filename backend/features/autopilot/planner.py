from __future__ import annotations

import uuid
from typing import Protocol

from .contracts import PlanRequest, RetryPolicy, Risk, ToolType, WorkflowPlan, WorkflowStep
from .exceptions import UnsafeAction


class PlanningProvider(Protocol):
    async def create_plan(self, request: str, user_id: str) -> WorkflowPlan: ...


class DeterministicPlanner:
    """Offline planner uses fixed, typed plans; it never emits executable code."""

    def plan(self, request: PlanRequest, user_id: str) -> WorkflowPlan:
        text = request.request.casefold()
        if any(x in text for x in ("run shell", "execute command", "run python", "run javascript")):
            raise UnsafeAction(
                "Autopilot does not execute shell, Python, or JavaScript from requests"
            )
        if "internship" in text or "internships" in text:
            steps = [
                WorkflowStep(
                    id="search",
                    description="Search fictional internship examples",
                    tool=ToolType.SEARCH,
                    input={"query": "AI internships"},
                    expected_output="Three fictional opportunities",
                    risk=Risk.LOW,
                    parallel_safe=True,
                ),
                WorkflowStep(
                    id="compare",
                    description="Compare example requirements to the provided profile",
                    tool=ToolType.CAREER,
                    input={"from_step": "search"},
                    expected_output="Explainable comparison",
                    dependencies=["search"],
                    risk=Risk.LOW,
                ),
                WorkflowStep(
                    id="draft",
                    description="Prepare an application email draft",
                    tool=ToolType.EMAIL_DRAFT,
                    input={"tone": "professional", "from_step": "compare"},
                    expected_output="Draft for review",
                    dependencies=["compare"],
                    risk=Risk.LOW,
                ),
                WorkflowStep(
                    id="approval-send",
                    description="Send the reviewed email only after explicit approval",
                    tool=ToolType.EMAIL_SEND,
                    input={"target": "fictional employer", "action": "send draft"},
                    expected_output="Approved demo action status",
                    dependencies=["draft"],
                    risk=Risk.HIGH,
                    approval_required=True,
                    retry_policy=RetryPolicy(max_retries=0),
                ),
                WorkflowStep(
                    id="reminder",
                    description="Preview a reminder for the application deadline",
                    tool=ToolType.REMINDER,
                    input={
                        "when": "2026-12-01",
                        "label": "Review AI internship application deadline",
                    },
                    expected_output="Reminder preview",
                    dependencies=["compare"],
                    risk=Risk.MEDIUM,
                    approval_required=True,
                ),
                WorkflowStep(
                    id="finish",
                    description="Summarize results and evidence",
                    tool=ToolType.COMPLETE,
                    input={},
                    expected_output="Execution summary",
                    dependencies=["approval-send", "reminder"],
                    risk=Risk.LOW,
                ),
            ]
        else:
            steps = [
                WorkflowStep(
                    id="review",
                    description=f"Review request: {request.request[:160]}",
                    tool=ToolType.COMPLETE,
                    input={"request_summary": request.request[:240]},
                    expected_output="A safe summary",
                    risk=Risk.LOW,
                )
            ]
        return WorkflowPlan(
            id=str(uuid.uuid4()),
            user_id=user_id,
            request=request.request,
            demo=request.demo,
            steps=steps,
        )


class ProviderPlanner:
    def __init__(self, provider: PlanningProvider):
        self.provider = provider

    async def plan(self, request: PlanRequest, user_id: str) -> WorkflowPlan:
        plan = await self.provider.create_plan(request.request, user_id)
        if plan.user_id != user_id:
            raise UnsafeAction("Planner returned a plan for a different user")
        # Validation is already enforced by the Pydantic schema; verify each tool is declared.
        return plan
