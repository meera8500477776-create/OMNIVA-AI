from .contracts import Risk, ToolType, WorkflowPlan
from .exceptions import UnsafeAction

MINIMUM_RISK = {
    ToolType.SEARCH: Risk.LOW,
    ToolType.CAREER: Risk.LOW,
    ToolType.EMAIL_DRAFT: Risk.LOW,
    ToolType.EMAIL_SEND: Risk.HIGH,
    ToolType.REMINDER: Risk.MEDIUM,
    ToolType.BROWSER_READ: Risk.MEDIUM,
    ToolType.BROWSER_FILL: Risk.MEDIUM,
    ToolType.DESKTOP: Risk.HIGH,
    ToolType.TUTOR: Risk.LOW,
    ToolType.VOICE: Risk.MEDIUM,
    ToolType.COMPANION: Risk.LOW,
    ToolType.AVATAR: Risk.LOW,
    ToolType.NOTIFY: Risk.MEDIUM,
    ToolType.CONDITION: Risk.LOW,
    ToolType.DELAY: Risk.LOW,
    ToolType.COMPLETE: Risk.LOW,
}
LEVEL = {Risk.LOW: 0, Risk.MEDIUM: 1, Risk.HIGH: 2}


def validate_plan_safety(plan: WorkflowPlan) -> None:
    for step in plan.steps:
        minimum = MINIMUM_RISK[step.tool]
        if LEVEL[step.risk] < LEVEL[minimum]:
            raise UnsafeAction(f"Tool {step.tool.value} is classified below its minimum risk")
        if step.risk in {Risk.MEDIUM, Risk.HIGH} and not step.approval_required:
            raise UnsafeAction("Medium- and high-risk steps require explicit approval")
        if step.risk == Risk.HIGH and step.retry_policy.max_retries:
            raise UnsafeAction("High-risk actions cannot be retried")
