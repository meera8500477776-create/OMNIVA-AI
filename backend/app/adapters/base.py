from datetime import datetime
from typing import Protocol
from uuid import UUID


class FeatureAdapter(Protocol):
    """Application boundary for AI providers; adapters must honor deadlines/cancellation."""

    async def create_session(self, user_id: UUID, payload: dict) -> dict: ...


class ProviderUnavailable(RuntimeError):
    pass


class AdapterResult(dict):
    """Normalized provider-neutral adapter result."""


def utc_iso(value: datetime) -> str:
    return value.isoformat()
