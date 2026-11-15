from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .exceptions import Conflict, Forbidden, NotFound


@dataclass
class Approval:
    id: str
    user_id: str
    workflow_id: str
    step_id: str
    plan_hash: str
    action_text: str
    action_hash: str
    expires_at: datetime
    status: str = "pending"


class ApprovalManager:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self.items: dict[str, Approval] = {}

    def create(
        self,
        user_id: str,
        workflow_id: str,
        step_id: str,
        plan_hash: str,
        action_text: str,
        action_hash: str,
    ) -> Approval:
        item = Approval(
            secrets.token_urlsafe(24),
            user_id,
            workflow_id,
            step_id,
            plan_hash,
            action_text,
            action_hash,
            datetime.now(UTC) + timedelta(seconds=self.ttl),
        )
        self.items[item.id] = item
        return item

    def _owned(self, approval_id, user_id) -> Approval:
        item = self.items.get(approval_id)
        if item is None:
            raise NotFound("Approval request was not found")
        if item.user_id != user_id:
            raise Forbidden("Approval request belongs to another user")
        if item.expires_at <= datetime.now(UTC):
            item.status = "expired"
            raise Conflict("Approval request expired")
        return item

    def decide(
        self,
        approval_id: str,
        user_id: str,
        *,
        plan_hash: str,
        action_hash: str,
        confirmed: bool,
        action_text: str,
    ) -> Approval:
        item = self._owned(approval_id, user_id)
        if item.status != "pending":
            raise Conflict("Approval request is no longer pending")
        if not secrets.compare_digest(item.plan_hash, plan_hash):
            raise Conflict("Plan changed; request a new approval")
        if action_text != item.action_text or not secrets.compare_digest(
            item.action_hash, action_hash
        ):
            raise Conflict("The approved action or target does not match the request")
        item.status = "approved" if confirmed else "denied"
        return item

    def consume(
        self,
        approval_id: str,
        user_id: str,
        workflow_id: str,
        step_id: str,
        plan_hash: str,
        action_hash: str,
    ) -> None:
        item = self._owned(approval_id, user_id)
        if (item.workflow_id, item.step_id, item.plan_hash) != (workflow_id, step_id, plan_hash):
            raise Conflict("Approval is bound to a different action")
        if not secrets.compare_digest(item.action_hash, action_hash):
            raise Conflict("Action payload changed after approval")
        if item.status != "approved":
            raise Conflict("Explicit approval is required before this action")
        item.status = "consumed"

    def cancel_workflow(self, workflow_id: str, user_id: str) -> None:
        for item in self.items.values():
            if (
                item.workflow_id == workflow_id
                and item.user_id == user_id
                and item.status == "pending"
            ):
                item.status = "cancelled"

    def status(self, approval_id: str, user_id: str) -> str:
        return self._owned(approval_id, user_id).status

    def list_for_user(self, user_id: str):
        return [a for a in self.items.values() if a.user_id == user_id]
