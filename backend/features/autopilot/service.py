from __future__ import annotations

import asyncio

from .approvals import ApprovalManager
from .browser_adapter import BrowserAutomationAdapter
from .contracts import PlanRequest, WorkflowPlan
from .demo_provider import register_demo_tools
from .exceptions import CapabilityUnavailable, Forbidden, NotFound, ProviderTimeout
from .memory_adapter import MemoryAdapter
from .orchestrator import WorkflowOrchestrator
from .planner import DeterministicPlanner, PlanningProvider, ProviderPlanner
from .tool_registry import ToolRegistry


class AutopilotService:
    def __init__(
        self,
        *,
        registry: ToolRegistry | None = None,
        approvals: ApprovalManager | None = None,
        orchestrator: WorkflowOrchestrator | None = None,
        memory: MemoryAdapter | None = None,
        planner: PlanningProvider | None = None,
        browser: BrowserAutomationAdapter | None = None,
        planning_timeout: float = 10.0,
    ):
        self.approvals = approvals or ApprovalManager()
        self.registry = registry or register_demo_tools(ToolRegistry())
        self.orchestrator = orchestrator or WorkflowOrchestrator(self.registry, self.approvals)
        self.memory = memory or MemoryAdapter()
        self.planner_provider = planner
        self.deterministic = DeterministicPlanner()
        self.browser = browser or BrowserAutomationAdapter(demo=True)
        self.planning_timeout = max(0.1, min(60.0, planning_timeout))
        self.plans: dict[str, WorkflowPlan] = {}

    async def create_plan(self, request: PlanRequest, user_id: str) -> WorkflowPlan:
        if request.demo:
            plan = self.deterministic.plan(request, user_id)
        elif self.planner_provider:
            try:
                plan = await asyncio.wait_for(
                    ProviderPlanner(self.planner_provider).plan(request, user_id),
                    timeout=self.planning_timeout,
                )
            except TimeoutError as exc:
                raise ProviderTimeout("Planning provider timed out") from exc
        else:
            raise CapabilityUnavailable("Live planning provider is not configured")
        if plan.user_id != user_id:
            raise Forbidden("Plan ownership does not match the authenticated user")
        self.plans[plan.id] = plan
        return plan

    def get_plan(self, plan_id: str, user_id: str) -> WorkflowPlan:
        plan = self.plans.get(plan_id)
        if not plan:
            raise NotFound("Plan was not found")
        if plan.user_id != user_id:
            raise Forbidden("Plan belongs to another user")
        return plan

    def create_workflow(self, plan_id: str, user_id: str):
        plan = self.get_plan(plan_id, user_id)
        return self.orchestrator.create(plan)

    def workflow(self, workflow_id, user_id):
        return self.orchestrator.get(workflow_id, user_id)

    def history(self, user_id):
        return self.orchestrator.repository.list(user_id)

    async def browser_evidence(self, workflow_id: str, user_id: str):
        # Confirm workflow ownership before returning evidence from the demo fixture.
        self.workflow(workflow_id, user_id)
        page = await self.browser.inspect("https://internships.demo.test/list")
        return [{"title": page["title"], "text": page["text"], "evidence_id": page["evidence_id"], "demo": page["demo"]}]

    def approvals_for_user(self, user_id):
        return [
            a for a in self.approvals.list_for_user(user_id) if a.status in {"pending", "approved"}
        ]
