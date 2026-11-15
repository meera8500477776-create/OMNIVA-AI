from __future__ import annotations

from typing import Any

FICTIONAL_OPPORTUNITIES = [
    {
        "id": "demo-ai-001",
        "company": "Northstar AI Research",
        "role": "AI Research Intern",
        "deadline": "2026-12-01",
        "skills": ["Python", "machine learning"],
        "fictional": True,
    },
    {
        "id": "demo-ai-002",
        "company": "Cedar Labs",
        "role": "ML Engineering Intern",
        "deadline": "2026-12-08",
        "skills": ["Python", "APIs", "data analysis"],
        "fictional": True,
    },
    {
        "id": "demo-ai-003",
        "company": "Example Robotics",
        "role": "Applied AI Intern",
        "deadline": "2026-12-15",
        "skills": ["Python", "robotics", "computer vision"],
        "fictional": True,
    },
]


class DemoTools:
    async def search(self, payload: dict[str, Any], key: str):
        return {"items": FICTIONAL_OPPORTUNITIES, "source": "local fictional fixture", "demo": True}

    async def compare(self, payload, key):
        items = (
            payload.get("upstream_results", {})
            .get("search", {})
            .get("items", FICTIONAL_OPPORTUNITIES)
        )
        return {
            "matches": [
                {
                    "opportunity": item["role"],
                    "illustrative_match_score": 0.6 + index * 0.1,
                    "matched_skills": ["Python"],
                    "rationale": "Illustrative rule-based comparison; not validated.",
                }
                for index, item in enumerate(items)
            ],
            "demo": True,
            "limitations": ["Illustrative scores are not scientifically validated."],
        }

    async def draft(self, payload, key):
        return {
            "subject": "Application — AI Internship (DEMO)",
            "body": "Hello,\n\nI am interested in the AI internship opportunity. My relevant skills include Python and machine learning. I would welcome the chance to discuss my background.\n\nBest regards,\n[Your name]",
            "status": "draft-preview",
            "sent": False,
            "demo": True,
        }

    async def send(self, payload, key):
        return {
            "status": "simulated-approved-action",
            "sent": False,
            "target": "fictional employer",
            "demo": True,
            "note": "No email was sent.",
        }

    async def reminder(self, payload, key):
        return {
            "status": "reminder-preview",
            "created": False,
            "label": payload.get("label", "Review deadline"),
            "when": payload.get("when"),
            "demo": True,
            "note": "No calendar event or notification was created.",
        }

    async def complete(self, payload, key):
        return {
            "summary": "Fictional internship results compared; demo email drafted; approved actions and reminder previews are labeled as simulations.",
            "demo": True,
        }


def register_demo_tools(registry):
    tools = DemoTools()
    from .contracts import ToolType

    for tool, handler, parallel in (
        (ToolType.SEARCH, tools.search, True),
        (ToolType.CAREER, tools.compare, False),
        (ToolType.EMAIL_DRAFT, tools.draft, False),
        (ToolType.EMAIL_SEND, tools.send, False),
        (ToolType.REMINDER, tools.reminder, False),
        (ToolType.BROWSER_READ, tools.search, False),
        (ToolType.COMPLETE, tools.complete, False),
    ):
        registry.register(tool, handler, parallel_safe=parallel, demo_only=True)
    return registry
