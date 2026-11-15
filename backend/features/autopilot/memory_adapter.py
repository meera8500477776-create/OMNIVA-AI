from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol

from .contracts import MemoryInput, MemoryRecord
from .exceptions import Forbidden, UnsafeAction

SECRET_PATTERNS = (
    re.compile(
        r"(?i)\b(password|passwd|secret|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|bearer)\b\s*[:=]\s*\S+"
    ),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
)


class MemoryRepository(Protocol):
    def list_for_user(self, user_id: str) -> list[MemoryRecord]: ...
    def save(self, record: MemoryRecord) -> None: ...
    def delete(self, user_id: str, memory_id: str) -> None: ...


class InMemoryMemoryRepository:
    def __init__(self):
        self.items: dict[str, MemoryRecord] = {}

    def list_for_user(self, user_id):
        return [m for m in self.items.values() if m.user_id == user_id]

    def save(self, record):
        self.items[record.id] = record

    def delete(self, user_id, memory_id):
        item = self.items.get(memory_id)
        if item and item.user_id == user_id:
            self.items.pop(memory_id)


class MemoryAdapter:
    """Consent defaults off; all memory keys are owner-scoped and expire."""

    def __init__(self, repository: MemoryRepository | None = None):
        self.repository = repository or InMemoryMemoryRepository()
        self.consent: set[str] = set()
        self.audit: list[dict[str, str]] = []

    def enable(self, user_id: str, consented: bool):
        if not consented:
            raise Forbidden("Explicit consent is required to enable memory")
        self.consent.add(user_id)
        self.audit.append({"user_id": user_id, "action": "memory.enabled"})

    def disable(self, user_id: str):
        self.consent.discard(user_id)
        self.audit.append({"user_id": user_id, "action": "memory.disabled"})

    def _clean(self, user_id: str):
        now = datetime.now(UTC)
        for item in self.repository.list_for_user(user_id):
            if item.expires_at <= now:
                self.repository.delete(user_id, item.id)
                self.audit.append(
                    {"user_id": user_id, "action": "memory.expired", "memory_id": item.id}
                )

    def add(self, user_id: str, payload: MemoryInput) -> MemoryRecord:
        if user_id not in self.consent:
            raise Forbidden("Memory is disabled until you explicitly consent")
        if any(pattern.search(payload.content) for pattern in SECRET_PATTERNS):
            raise UnsafeAction(
                "Memory cannot contain passwords, credentials, tokens, or payment card numbers"
            )
        now = datetime.now(UTC)
        item = MemoryRecord(
            id=secrets.token_urlsafe(16),
            user_id=user_id,
            content=payload.content,
            provenance=payload.provenance,
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(days=payload.retention_days),
        )
        self.repository.save(item)
        self.audit.append({"user_id": user_id, "action": "memory.created", "memory_id": item.id})
        return item

    def retrieve(self, user_id: str, query: str = "") -> list[MemoryRecord]:
        if user_id not in self.consent:
            raise Forbidden("Memory is disabled until you explicitly consent")
        self._clean(user_id)
        needle = query.casefold()
        items = self.repository.list_for_user(user_id)
        return [
            item
            for item in items
            if not needle or needle in (item.content + " " + item.provenance).casefold()
        ]

    def update(self, user_id: str, memory_id: str, payload: MemoryInput) -> MemoryRecord:
        if user_id not in self.consent:
            raise Forbidden("Memory is disabled until you explicitly consent")
        old = next(
            (item for item in self.repository.list_for_user(user_id) if item.id == memory_id), None
        )
        if old is None:
            raise Forbidden("Memory was not found for this user")
        if any(pattern.search(payload.content) for pattern in SECRET_PATTERNS):
            raise UnsafeAction(
                "Memory cannot contain passwords, credentials, tokens, or payment card numbers"
            )
        now = datetime.now(UTC)
        updated = MemoryRecord(
            id=old.id,
            user_id=user_id,
            content=payload.content,
            provenance=payload.provenance,
            created_at=old.created_at,
            updated_at=now,
            expires_at=now + timedelta(days=payload.retention_days),
        )
        self.repository.save(updated)
        self.audit.append({"user_id": user_id, "action": "memory.updated", "memory_id": memory_id})
        return updated

    def delete(self, user_id: str, memory_id: str) -> None:
        if not any(item.id == memory_id for item in self.repository.list_for_user(user_id)):
            raise Forbidden("Memory was not found for this user")
        self.repository.delete(user_id, memory_id)
        self.audit.append({"user_id": user_id, "action": "memory.deleted", "memory_id": memory_id})

    def delete_all(self, user_id: str) -> None:
        for item in self.repository.list_for_user(user_id):
            self.repository.delete(user_id, item.id)
        self.disable(user_id)
        self.audit.append({"user_id": user_id, "action": "memory.deleted_all"})
