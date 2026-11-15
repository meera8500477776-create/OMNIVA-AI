import asyncio
import json

import pytest

from features.ai_adapters.gemini_features import GeminiWorkflowPlanner
from features.autopilot.exceptions import UnsafeAction


def test_autopilot_gemini_plan_binds_owner_and_requires_external_action_approval():
    class FakeProvider:
        async def generate(self, **_kwargs):
            return json.dumps({"steps": [{
                "id": "send", "description": "Send an email", "tool": "email_send",
                "input": {"target": "recipient"}, "expected_output": "Sent message",
                "dependencies": [], "risk": "low", "approval_required": False,
            }]})

    planner = GeminiWorkflowPlanner(FakeProvider())
    with pytest.raises(UnsafeAction, match="without explicit approval"):
        asyncio.run(planner.create_plan("Send an email", "owner-id"))
