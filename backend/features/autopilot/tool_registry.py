from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .contracts import ToolType, WorkflowStep
from .exceptions import CapabilityUnavailable, UnsafeAction

ToolHandler = Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolSpec:
    handler: ToolHandler
    parallel_safe: bool = False
    demo_only: bool = False


class ToolRegistry:
    def __init__(self, max_output_bytes: int = 20000):
        self._tools = {}
        self.max_output_bytes = max_output_bytes

    def register(
        self, tool: ToolType, handler: ToolHandler, *, parallel_safe=False, demo_only=False
    ):
        self._tools[tool] = ToolSpec(handler, parallel_safe, demo_only)

    def get(self, tool: ToolType) -> ToolSpec:
        spec = self._tools.get(tool)
        if spec is None:
            raise CapabilityUnavailable(f"Tool {tool.value} is unavailable")
        return spec

    async def execute(
        self,
        step: WorkflowStep,
        idempotency_key: str,
        *,
        demo: bool,
        input_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        spec = self.get(step.tool)
        if spec.demo_only and not demo:
            raise CapabilityUnavailable(f"{step.tool.value} is unavailable in live mode")
        if step.parallel_safe and not spec.parallel_safe:
            raise UnsafeAction("Step requested unsafe parallel execution")
        if step.risk.value == "high" and step.retry_policy.max_retries:
            raise UnsafeAction("Irreversible steps cannot be retried")
        result = await spec.handler(
            input_override if input_override is not None else step.input, idempotency_key
        )
        try:
            size = len(json.dumps(result, ensure_ascii=False).encode())
        except (TypeError, ValueError) as exc:
            raise UnsafeAction("Tool returned a non-serializable result") from exc
        if size > self.max_output_bytes:
            raise UnsafeAction("Tool result exceeded the output size limit")
        return result
