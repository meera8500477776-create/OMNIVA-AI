"""Thin, feature-specific prompts over the shared Gemini client."""

from __future__ import annotations

import json
from uuid import uuid4

from features.autopilot.contracts import Risk, ToolType, WorkflowPlan, WorkflowStep
from features.autopilot.exceptions import (
    CapabilityUnavailable,
    ProviderFailure,
    ProviderRateLimited,
    ProviderTimeout,
    UnsafeAction,
)

from .gemini import GeminiError, GeminiProvider


class GeminiCompanion:
    def __init__(self, provider: GeminiProvider, user_id: str):
        self.provider, self.user_id = provider, user_id

    async def respond(self, messages: list[dict[str, str]], persona: str, locale: str) -> str:
        history = messages[-12:]
        return await self.provider.generate(
            feature="care_companion",
            user_id=self.user_id,
            system=(
                f"You are an AI care companion, never a human. Persona style: {persona}. "
                f"Reply in the user's language (locale {locale}). Be supportive and non-exclusive; "
                "do not diagnose, make guarantees, or discourage professional support. Keep replies concise."
            ),
            messages=[{"role": item["role"], "text": item.get("content", item.get("text", ""))} for item in history],
        )


class GeminiWorkflowPlanner:
    def __init__(self, provider: GeminiProvider):
        self.provider = provider

    async def create_plan(self, request: str, user_id: str) -> WorkflowPlan:
        try:
            raw = await self.provider.generate(
            feature="autopilot_planning",
            user_id=user_id,
            system=(
                "Create a JSON object with only a 'steps' array for a reviewable plan. "
                "Use only tools search, career, email_draft, email_send, reminder, browser_read, "
                "browser_fill, tutor, voice, companion, notify, delay, complete. Never use shell, "
                "code execution, desktop control, or fabricate credentials. External actions require "
                "approval_required=true and risk=high. A step has id, description, tool, input, "
                "expected_output, dependencies, risk, approval_required. Return at most 12 steps."
            ),
            messages=[{"role": "user", "text": request}],
            json_mode=True,
            )
        except GeminiError as exc:
            if exc.code == "provider_unavailable":
                raise CapabilityUnavailable("Gemini planning provider is not configured") from None
            if exc.code == "provider_timeout":
                raise ProviderTimeout("Gemini planning timed out") from None
            if exc.code in {"usage_limit", "provider_rate_limited"}:
                raise ProviderRateLimited("Gemini request limit reached") from None
            if exc.status_code >= 500:
                raise ProviderFailure("Gemini planning provider failed") from None
            raise CapabilityUnavailable(str(exc)) from None
        try:
            data = json.loads(raw)
            raw_steps = data["steps"]
            if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= 12:
                raise ValueError
            steps = [WorkflowStep.model_validate(item) for item in raw_steps]
        except (ValueError, KeyError, TypeError):
            raise UnsafeAction("Gemini returned a plan that did not match the workflow contract") from None
        sensitive = {ToolType.EMAIL_SEND, ToolType.BROWSER_FILL, ToolType.REMINDER, ToolType.NOTIFY}
        for step in steps:
            if step.tool in sensitive and (step.risk != Risk.HIGH or not step.approval_required):
                raise UnsafeAction("Gemini returned an external action without explicit approval")
        return WorkflowPlan(
            id=str(uuid4()), user_id=user_id, request=request, demo=False, steps=steps
        )
