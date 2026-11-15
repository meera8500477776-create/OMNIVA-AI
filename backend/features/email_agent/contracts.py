from dataclasses import dataclass, field
from enum import StrEnum

class Category(StrEnum):
    IMPORTANT = "important"
    URGENT = "urgent"
    NORMAL = "normal"
    PROMOTIONS = "promotions"
    SPAM_SUSPECTED = "spam-suspected"

class Tone(StrEnum):
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    CONCISE = "concise"
    FORMAL = "formal"

@dataclass(frozen=True)
class Email:
    id: str
    sender: str
    subject: str
    body: str
    unread: bool = True
    thread_id: str | None = None

@dataclass(frozen=True)
class EmailView:
    email: Email
    category: Category
    summary: str
    injection_suspected: bool = False
    suggested_actions: tuple[str, ...] = field(default_factory=tuple)

@dataclass(frozen=True)
class Draft:
    email_id: str
    body: str
    tone: Tone
    demo: bool

class ProviderUnavailable(RuntimeError): pass
class ApprovalRequired(PermissionError): pass
class DuplicateSend(RuntimeError): pass
