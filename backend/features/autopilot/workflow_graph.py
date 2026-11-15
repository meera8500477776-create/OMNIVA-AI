from .contracts import WorkflowDefinition, WorkflowPlan
from .exceptions import UnsafeAction


def topological_order(plan: WorkflowPlan) -> list[str]:
    graph = {step.id: set(step.dependencies) for step in plan.steps}
    result = []
    while graph:
        ready = sorted(node for node, deps in graph.items() if not deps)
        if not ready:
            raise UnsafeAction("Workflow contains a dependency cycle")
        result.extend(ready)
        for node in ready:
            graph.pop(node)
        for deps in graph.values():
            deps.difference_update(ready)
    return result


def validate_definition(flow: WorkflowDefinition) -> list[str]:
    ids = [node.id for node in flow.nodes]
    if len(ids) != len(set(ids)):
        raise UnsafeAction("Workflow node IDs must be unique")
    graph = {n.id: set(n.dependencies) for n in flow.nodes}
    known = set(ids)
    if any(deps - known for deps in graph.values()):
        raise UnsafeAction("Workflow references an unknown node")
    ordered = []
    while graph:
        ready = sorted(n for n, d in graph.items() if not d)
        if not ready:
            raise UnsafeAction("Workflow definition contains a cycle")
        ordered.extend(ready)
        for n in ready:
            graph.pop(n)
        for d in graph.values():
            d.difference_update(ready)
    return ordered
