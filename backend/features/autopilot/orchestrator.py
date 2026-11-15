from __future__ import annotations

import asyncio
import hashlib
import json

from .approvals import ApprovalManager
from .contracts import StepStatus, WorkflowPlan, WorkflowStatus
from .exceptions import Conflict
from .persistence import InMemoryWorkflowRepository, WorkflowRepository, WorkflowRun, event
from .safety import validate_plan_safety
from .tool_registry import ToolRegistry
from .workflow_graph import topological_order


class WorkflowOrchestrator:
    def __init__(
        self,
        registry: ToolRegistry,
        approvals: ApprovalManager,
        repository: WorkflowRepository | None = None,
        max_parallel: int = 4,
    ):
        self.registry, self.approvals = registry, approvals
        self.repository = repository or InMemoryWorkflowRepository()
        self.max_parallel = max(1, min(4, max_parallel))
        self._locks = {}
        self._tasks = {}
        self.emergency_stopped_users = set()

    def emergency_stop(self, user_id: str):
        self.emergency_stopped_users.add(user_id)
        for run in self.repository.list(user_id):
            if run.status in {
                WorkflowStatus.RUNNING,
                WorkflowStatus.PAUSED,
                WorkflowStatus.WAITING_APPROVAL,
            }:
                self.cancel(run.id, user_id)

    def release_emergency_stop(self, user_id: str, confirmed: bool):
        if not confirmed:
            raise Conflict("Explicit confirmation is required to release emergency stop")
        self.emergency_stopped_users.discard(user_id)

    def create(self, plan: WorkflowPlan) -> WorkflowRun:
        topological_order(plan)
        validate_plan_safety(plan)
        digest = plan.integrity_hash()
        run = WorkflowRun(plan, plan.user_id, digest)
        self.repository.create(run)
        event(run, "created", "Workflow plan created", plan_hash=digest)
        self.repository.save(run)
        return run

    def get(self, workflow_id: str, user_id: str) -> WorkflowRun:
        return self.repository.get(workflow_id, user_id)

    def resolve_approval(
        self, approval_id, user_id, *, plan_hash, action_hash, confirmed, action_text
    ):
        item = self.approvals.decide(
            approval_id,
            user_id,
            plan_hash=plan_hash,
            action_hash=action_hash,
            confirmed=confirmed,
            action_text=action_text,
        )
        run = self.get(item.workflow_id, user_id)
        step = next(step for step in run.plan.steps if step.id == item.step_id)
        if not confirmed:
            step.status = StepStatus.SKIPPED
            step.error_code = "approval_denied"
            event(run, "approval_denied", "User denied this action", step.id)
            run.status = WorkflowStatus.RUNNING
            self.repository.save(run)
        else:
            event(run, "approval_granted", "User approved the displayed action", step.id)
        return item

    def events(self, workflow_id, user_id):
        return list(self.get(workflow_id, user_id).events)

    def pause(self, workflow_id, user_id):
        run = self.get(workflow_id, user_id)
        if run.status not in {WorkflowStatus.RUNNING, WorkflowStatus.WAITING_APPROVAL}:
            raise Conflict("Only an active workflow can be paused")
        run.pause_requested = True
        run.status = WorkflowStatus.PAUSED
        event(run, "paused", "Workflow paused at a safe checkpoint")
        self.repository.save(run)
        return run

    def resume(self, workflow_id, user_id):
        run = self.get(workflow_id, user_id)
        if run.status != WorkflowStatus.PAUSED:
            raise Conflict("Workflow is not paused")
        run.pause_requested = False
        run.status = WorkflowStatus.RUNNING
        event(run, "resumed", "Workflow resumed")
        self.repository.save(run)
        return run

    def cancel(self, workflow_id, user_id):
        run = self.get(workflow_id, user_id)
        if run.status in {WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED}:
            return run
        run.cancel_requested = True
        run.status = WorkflowStatus.CANCELLED
        self.approvals.cancel_workflow(run.id, user_id)
        task = self._tasks.get(run.id)
        try:
            current = asyncio.current_task()
        except RuntimeError:
            current = None
        if task and task is not current:
            task.cancel()
        for step in run.plan.steps:
            if step.status in {StepStatus.PENDING, StepStatus.WAITING_APPROVAL}:
                step.status = StepStatus.CANCELLED
        event(run, "cancelled", "Workflow cancelled; no new actions will start")
        self.repository.save(run)
        return run

    async def start(self, workflow_id, user_id):
        run = self.get(workflow_id, user_id)
        lock = self._locks.setdefault(run.id, asyncio.Lock())
        async with lock:
            run = self.get(workflow_id, user_id)
            if user_id in self.emergency_stopped_users:
                raise Conflict("Autopilot emergency stop is active")
            if run.status in {
                WorkflowStatus.COMPLETED,
                WorkflowStatus.CANCELLED,
                WorkflowStatus.FAILED,
                WorkflowStatus.PARTIAL,
            }:
                return run
            run.status = WorkflowStatus.RUNNING
            self.repository.save(run)
            event(run, "started", "Workflow execution started")
            task = asyncio.current_task()
            self._tasks[run.id] = task
            try:
                await self._drive(run)
            except asyncio.CancelledError:
                run.status = WorkflowStatus.CANCELLED
                for step in run.plan.steps:
                    if step.status in {
                        StepStatus.PENDING,
                        StepStatus.RUNNING,
                        StepStatus.WAITING_APPROVAL,
                    }:
                        step.status = StepStatus.CANCELLED
                event(run, "cancelled", "Workflow execution was cancelled")
                self.repository.save(run)
                raise
            except Exception as exc:
                run.status = WorkflowStatus.FAILED
                event(
                    run,
                    "failed",
                    "Workflow failed; internal details are redacted",
                    error_code=getattr(exc, "code", "workflow_failed"),
                )
                self.repository.save(run)
                raise
            finally:
                if self._tasks.get(run.id) is task:
                    self._tasks.pop(run.id, None)
            self.repository.save(run)
            return run

    async def _drive(self, run):
        hash_now = run.plan.integrity_hash()
        if hash_now != run.plan_hash:
            raise Conflict("Workflow plan integrity check failed")
        while True:
            if run.owner_id in self.emergency_stopped_users:
                run.cancel_requested = True
            if run.cancel_requested:
                run.status = WorkflowStatus.CANCELLED
                return
            if run.pause_requested:
                run.status = WorkflowStatus.PAUSED
                return
            by_id = {s.id: s for s in run.plan.steps}
            for step in run.plan.steps:
                if step.status == StepStatus.PENDING and any(
                    by_id[d].status in {StepStatus.FAILED, StepStatus.SKIPPED, StepStatus.CANCELLED}
                    for d in step.dependencies
                ):
                    step.status = StepStatus.SKIPPED
                    event(run, "step_skipped", "A dependency did not complete", step.id)
            pending = [
                s
                for s in run.plan.steps
                if s.status in {StepStatus.PENDING, StepStatus.WAITING_APPROVAL}
            ]
            if not pending:
                statuses = {s.status for s in run.plan.steps}
                run.status = (
                    WorkflowStatus.PARTIAL
                    if StepStatus.FAILED in statuses or StepStatus.SKIPPED in statuses
                    else WorkflowStatus.COMPLETED
                )
                event(
                    run,
                    "completed" if run.status == WorkflowStatus.COMPLETED else "partial",
                    "Workflow finished with recorded results",
                )
                return
            ready = [
                s
                for s in pending
                if all(by_id[d].status == StepStatus.SUCCEEDED for d in s.dependencies)
            ]
            if not ready:
                waiting = [s for s in pending if s.status == StepStatus.WAITING_APPROVAL]
                if waiting:
                    run.status = WorkflowStatus.WAITING_APPROVAL
                    self.repository.save(run)
                    return
                run.status = WorkflowStatus.PARTIAL
                return
            batch = []
            ran = False
            for step in ready:
                resolved_input = {
                    **step.input,
                    "upstream_results": {dep: by_id[dep].result for dep in step.dependencies},
                }
                if step.approval_required:
                    action_object = {
                        "tool": step.tool.value,
                        "description": step.description,
                        **resolved_input,
                    }
                    action_json = json.dumps(
                        action_object, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    )
                    action_text = f"Confirm this exact action and target: {action_json}"
                    if len(action_text) > 5000:
                        raise Conflict("Action is too large to present for explicit approval")
                    action_hash = hashlib.sha256(action_json.encode()).hexdigest()
                    if not step.approval_id:
                        approval = self.approvals.create(
                            run.owner_id, run.id, step.id, run.plan_hash, action_text, action_hash
                        )
                        step.approval_id = approval.id
                        step.status = StepStatus.WAITING_APPROVAL
                        event(
                            run,
                            "approval_required",
                            "Review the exact action and target before continuing",
                            step.id,
                            approval_id=approval.id,
                            action_hash=action_hash,
                        )
                        continue
                    approval_status = self.approvals.status(step.approval_id, run.owner_id)
                    if approval_status == "pending":
                        step.status = StepStatus.WAITING_APPROVAL
                        continue
                    self.approvals.consume(
                        step.approval_id,
                        run.owner_id,
                        run.id,
                        step.id,
                        run.plan_hash,
                        action_hash,
                    )
                if (
                    step.parallel_safe
                    and step.risk.value != "high"
                    and len(batch) < self.max_parallel
                ):
                    batch.append(step)
                else:
                    if batch:
                        await self._run_batch(run, batch)
                        ran = True
                        batch = []
                    await self._run_one(run, step)
                    ran = True
            if batch:
                await self._run_batch(run, batch)
                ran = True
            if not ran:
                run.status = (
                    WorkflowStatus.WAITING_APPROVAL
                    if any(s.status == StepStatus.WAITING_APPROVAL for s in run.plan.steps)
                    else WorkflowStatus.PARTIAL
                )
                self.repository.save(run)
                return
            if run.status == WorkflowStatus.PAUSED:
                return
            self.repository.save(run)

    async def _run_batch(self, run, steps):
        by_id = {step.id: step for step in run.plan.steps}
        await asyncio.gather(
            *(
                self._run_one(
                    run,
                    step,
                    {
                        **step.input,
                        "upstream_results": {dep: by_id[dep].result for dep in step.dependencies},
                    },
                )
                for step in steps
            )
        )

    async def _run_one(self, run, step, resolved_input=None):
        key = f"{run.id}:{step.id}"
        if key in run.idempotency_results:
            step.result = run.idempotency_results[key]
            step.status = StepStatus.SUCCEEDED
            return
        step.status = StepStatus.RUNNING
        step.attempts += 1
        event(run, "step_started", step.description, step.id, attempt=step.attempts)
        self.repository.save(run)
        retries = step.retry_policy.max_retries if step.risk.value != "high" else 0
        while True:
            try:
                result = await asyncio.wait_for(
                    self.registry.execute(
                        step,
                        key,
                        demo=run.plan.demo,
                        input_override=resolved_input,
                    ),
                    timeout=step.timeout_seconds,
                )
                step.result = result
                step.status = StepStatus.SUCCEEDED
                run.idempotency_results[key] = result
                event(run, "step_succeeded", "Step completed", step.id, attempt=step.attempts)
                return
            except asyncio.CancelledError:
                step.status = StepStatus.CANCELLED
                raise
            except Exception as exc:
                step.error_code = (
                    "step_timeout"
                    if isinstance(exc, TimeoutError)
                    else getattr(exc, "code", "tool_failed")
                )
                if step.attempts <= retries:
                    step.attempts += 1
                    await asyncio.sleep(step.retry_policy.backoff_seconds)
                    continue
                step.status = StepStatus.FAILED
                event(
                    run,
                    "step_failed",
                    "Step failed; details are redacted",
                    step.id,
                    error_code=step.error_code,
                )
                return
