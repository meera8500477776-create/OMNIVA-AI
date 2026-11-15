"""Original OMNIVA-owned illustrative career matcher; no reference code/data imported."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from .common import AdapterError, new_id, utc_now


@dataclass(frozen=True, slots=True)
class CareerProfile:
    education_level: str
    interests: tuple[str, ...]
    skills: tuple[str, ...]
    constraints: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CareerPath:
    domain: str
    role: str
    specialization: str
    skills: tuple[str, ...]
    interests: tuple[str, ...]
    roadmap: tuple[str, ...]


# Original, intentionally small illustrative taxonomy. Not sourced from the unlicensed repository.
_PATHS: tuple[CareerPath, ...] = (
    CareerPath("Technology", "Software Developer", "Web Applications",
               ("python", "problem solving", "communication"), ("building", "technology", "logic"),
               ("Learn programming fundamentals", "Build a small web project", "Seek mentor feedback")),
    CareerPath("Technology", "Data Analyst", "Product Analytics",
               ("spreadsheets", "statistics", "communication"), ("patterns", "numbers", "research"),
               ("Practice spreadsheet analysis", "Learn basic statistics", "Explain one dataset")),
    CareerPath("Creative Industries", "UX Designer", "Accessible Interfaces",
               ("visual design", "research", "communication"), ("design", "people", "building"),
               ("Study accessibility basics", "Interview users with consent", "Prototype a small interface")),
    CareerPath("Environment", "Sustainability Coordinator", "Community Programs",
               ("research", "writing", "project planning"), ("environment", "people", "research"),
               ("Explore local sustainability work", "Practice evidence summaries", "Plan a small community project")),
)
ALIAS = {"coding": "python", "programming": "python", "data analysis": "statistics",
         "design": "visual design", "teamwork": "communication", "planning": "project planning"}


def _norm(values: tuple[str, ...] | list[str]) -> set[str]:
    return {ALIAS.get(v.strip().casefold(), v.strip().casefold()) for v in values if v.strip()}


class CareerRecommendationAdapter:
    taxonomy_version = "omniva-illustrative-2026-01"
    ruleset_version = "skill-interest-overlap-v1"
    disclaimer = ("Illustrative guidance only. Scores are rule-based fit indicators, not probabilities; "
                  "career outcomes are not scientifically validated or guaranteed.")

    def recommend(self, profile: CareerProfile) -> dict[str, object]:
        if not profile.education_level.strip():
            raise AdapterError("invalid_profile", "education_level is required", 422)
        interests, skills = _norm(profile.interests), _norm(profile.skills)
        if not interests and not skills:
            raise AdapterError("insufficient_profile", "Provide at least one skill or interest", 422)
        matches: list[dict[str, object]] = []
        for path in _PATHS:
            required = set(path.skills)
            overlap = skills & required
            gaps = sorted(required - skills)
            skill_fit = len(overlap) / len(required) if required else 0.0
            interest_fit = len(interests & set(path.interests)) / len(path.interests)
            # Transparent, bounded heuristic: skill coverage is 70%, interest overlap 30%.
            score = round(100 * (0.7 * skill_fit + 0.3 * interest_fit))
            reasons = []
            if overlap:
                reasons.append("Relevant skills: " + ", ".join(sorted(overlap)))
            matched_interests = interests & set(path.interests)
            if matched_interests:
                reasons.append("Related interests: " + ", ".join(sorted(matched_interests)))
            if not reasons:
                reasons.append("This path is included as an option to explore")
            matches.append({
                "domain": path.domain, "role": path.role, "specialization": path.specialization,
                "match_score": score, "score_kind": "illustrative_rule_based_fit",
                "rationale": reasons, "skill_gaps": gaps, "roadmap": list(path.roadmap),
            })
        matches.sort(key=lambda item: (-int(item["match_score"]), str(item["role"])))
        return {
            "recommendation_id": new_id(), "generated_at": utc_now(),
            "taxonomy_version": self.taxonomy_version, "ruleset_version": self.ruleset_version,
            "recommendations": matches, "limitations": [self.disclaimer, "Taxonomy is a small original demo sample.", "Education level and constraints are collected but do not change this demo score."],
            "mode": "demo", "simulation": True,
        }
