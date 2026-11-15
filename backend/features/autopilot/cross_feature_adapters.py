from __future__ import annotations

from typing import Any, Protocol

from .exceptions import CapabilityUnavailable

FEATURES = ("email", "calendar", "career", "tutor", "voice", "desktop", "care_companion", "avatar")


class FeatureAdapter(Protocol):
    async def invoke(
        self, action: str, payload: dict[str, Any], user_id: str
    ) -> dict[str, Any]: ...


class UnavailableFeatureAdapter:
    def __init__(self, name: str):
        self.name = name

    async def invoke(self, action, payload, user_id):
        raise CapabilityUnavailable(f"{self.name} integration is not configured")


class CrossFeatureAdapters:
    def __init__(self, adapters: dict[str, FeatureAdapter] | None = None):
        self.adapters = {name: UnavailableFeatureAdapter(name) for name in FEATURES}
        self.adapters.update(adapters or {})

    async def invoke(self, name: str, action: str, payload: dict[str, Any], user_id: str):
        if name not in self.adapters:
            raise CapabilityUnavailable("Requested OMNIVA feature adapter is unavailable")
        return await self.adapters[name].invoke(action, payload, user_id)
