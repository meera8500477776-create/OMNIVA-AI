from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.db.models import CareReminder
from app.db.session import get_session
from features.care_companion.contracts import PersonaId
from features.care_companion.conversation import Conversation
from features.care_companion.memory import ConsentMemory
from features.care_companion.personas import PERSONAS
from features.email_agent.contracts import (
    ApprovalRequired,
    DuplicateSend,
    ProviderUnavailable,
    Tone,
)
from features.email_agent.demo_provider import DemoEmailProvider
from features.email_agent.service import EmailAgent

router = APIRouter(
    prefix="/features",
    tags=["Phase 4C feature adapters"],
    dependencies=[Depends(enforce_rate_limit)],
)


class DraftRequest(BaseModel):
    email_id: str = Field(min_length=1, max_length=100)
    tone: Tone = Tone.PROFESSIONAL


class EmailApprovalRequest(BaseModel):
    draft_id: str = Field(min_length=1, max_length=100)


class EmailSendRequest(BaseModel):
    approval: str = Field(min_length=1, max_length=200)


class CompanionStartRequest(BaseModel):
    persona: PersonaId
    locale: str = Field(default="en", min_length=2, max_length=16)
    consent: bool = False


class CompanionTurnRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class CompanionPersonaRequest(BaseModel):
    persona: PersonaId


class MemoryConsentRequest(BaseModel):
    consent: bool


class MemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class ReminderRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(default="", max_length=500)
    reminder_type: str = Field(default="deadline", pattern="^(deadline|call_prompt)$")
    scheduled_at: datetime
    timezone_name: str = Field(min_length=1, max_length=80)
    quiet_start: str = Field(default="22:00", pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    quiet_end: str = Field(default="08:00", pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    consent: bool = False


class EmailState:
    def __init__(self) -> None:
        self.agent = EmailAgent(demo=True)
        self.drafts: dict[str, object] = {}


class CompanionState:
    def __init__(self) -> None:
        self.conversation = Conversation(demo=True)
        self.memory = ConsentMemory()


email_states: dict[str, EmailState] = {}
companion_states: dict[str, CompanionState] = {}


def email_state(user_id: str) -> EmailState:
    return email_states.setdefault(user_id, EmailState())


def companion_state(user_id: str) -> CompanionState:
    return companion_states.setdefault(user_id, CompanionState())


def state_for_session(user_id: str, session_id: str) -> CompanionState:
    ensure_demo()
    state = companion_states.get(user_id)
    if state is None or session_id not in state.conversation.sessions:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Session not found"}
        )
    return state


def ensure_demo() -> None:
    if settings.app_mode != "demo":
        raise HTTPException(
            status_code=503,
            detail={"code": "provider_unavailable", "message": "Live provider is not configured"},
        )


@router.get("/email-agent/inbox")
async def email_inbox(user: CurrentUser):
    ensure_demo()
    views = await email_state(str(user.id)).agent.inbox()
    return {
        "items": [asdict(item) for item in views],
        "demo": True,
        "label": "Fictional demonstration inbox",
    }


@router.post("/email-agent/drafts")
def create_email_draft(payload: DraftRequest, user: CurrentUser):
    ensure_demo()
    state = email_state(str(user.id))
    email = next((item for item in DemoEmailProvider.emails if item.id == payload.email_id), None)
    if email is None:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Message not found"}
        )
    draft = state.agent.draft(email, payload.tone)
    draft_id = str(uuid4())
    state.drafts[draft_id] = draft
    return {"draft_id": draft_id, **asdict(draft)}


@router.post("/email-agent/approvals")
def create_email_approval(payload: EmailApprovalRequest, user: CurrentUser):
    ensure_demo()
    state = email_state(str(user.id))
    if payload.draft_id not in state.drafts:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Draft not found"}
        )
    token = state.agent.request_send_approval(str(user.id), payload.draft_id)
    return {"approval": token, "draft_id": payload.draft_id, "status": "pending"}


@router.post("/email-agent/send")
async def send_approved_email(
    payload: EmailSendRequest,
    user: CurrentUser,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
):
    ensure_demo()
    state = email_state(str(user.id))
    try:
        result = await state.agent.send_approved(str(user.id), payload.approval, idempotency_key)
    except ApprovalRequired as exc:
        raise HTTPException(
            status_code=403, detail={"code": "approval_required", "message": str(exc)}
        ) from exc
    except ProviderUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"code": "provider_unavailable", "message": str(exc)}
        ) from exc
    except DuplicateSend as exc:
        raise HTTPException(
            status_code=409, detail={"code": "duplicate_action", "message": str(exc)}
        ) from exc
    return {"status": "simulated", "result": result, "sent": False, "demo": True}


@router.post("/email-agent/emergency-disable")
def disable_email_agent(user: CurrentUser):
    ensure_demo()
    email_state(str(user.id)).agent.disabled = True
    return {"disabled": True, "demo": True}


@router.get("/email-agent/activity")
def email_activity(user: CurrentUser):
    ensure_demo()
    return {"items": email_state(str(user.id)).agent.activity, "demo": True}


@router.get("/care-companion/personas")
def companion_personas(user: CurrentUser):
    ensure_demo()
    return {
        "items": [
            {
                "id": persona.value,
                "name": details.name,
                "greeting": details.greeting,
                "ai_identity": True,
            }
            for persona, details in PERSONAS.items()
        ],
        "demo": True,
    }


@router.post("/care-companion/sessions", status_code=201)
async def start_companion(payload: CompanionStartRequest, user: CurrentUser):
    ensure_demo()
    if not payload.consent:
        raise HTTPException(
            status_code=403, detail={"code": "consent_required", "message": "Consent is required"}
        )
    try:
        session = await companion_state(str(user.id)).conversation.start(
            payload.persona, payload.locale
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_locale", "message": str(exc)}
        ) from exc
    return {**asdict(session), "ai_identity": True, "persistence": "session memory only"}


@router.get("/care-companion/sessions/{session_id}")
def get_companion_session(session_id: str, user: CurrentUser):
    state = state_for_session(str(user.id), session_id)
    session = state.conversation.sessions[session_id]
    return {
        **asdict(session),
        "transcript": state.conversation.transcripts[session_id],
        "ai_identity": True,
    }


@router.post("/care-companion/sessions/{session_id}/turns")
async def companion_turn(session_id: str, payload: CompanionTurnRequest, user: CurrentUser):
    state = state_for_session(str(user.id), session_id)
    answer = await state.conversation.reply(session_id, payload.text)
    return {
        "answer": answer,
        "demo": True,
        "ai_identity": True,
        "transcript": state.conversation.transcripts[session_id],
    }


@router.post("/care-companion/sessions/{session_id}/persona")
def switch_companion_persona(session_id: str, payload: CompanionPersonaRequest, user: CurrentUser):
    state = state_for_session(str(user.id), session_id)
    state.conversation.switch(session_id, payload.persona)
    session = state.conversation.sessions[session_id]
    return {**asdict(session), "ai_identity": True}


@router.put("/care-companion/memory/consent")
def companion_memory_consent(payload: MemoryConsentRequest, user: CurrentUser):
    ensure_demo()
    memory = companion_state(str(user.id)).memory
    if payload.consent:
        memory.enable(True)
    else:
        memory.delete_all()
    return {"enabled": memory.enabled, "demo": True}


@router.post("/care-companion/memory")
def remember_companion_item(payload: MemoryRequest, user: CurrentUser):
    ensure_demo()
    memory = companion_state(str(user.id)).memory
    if not memory.enabled:
        raise HTTPException(
            status_code=403,
            detail={"code": "consent_required", "message": "Enable memory consent first"},
        )
    memory.remember(payload.content)
    return {"items": memory.items, "demo": True}


@router.get("/care-companion/memory")
def read_companion_memory(user: CurrentUser):
    ensure_demo()
    memory = companion_state(str(user.id)).memory
    return {"items": memory.items, "enabled": memory.enabled, "demo": True}


@router.delete("/care-companion/memory", status_code=204)
def delete_companion_memory(user: CurrentUser):
    ensure_demo()
    companion_state(str(user.id)).memory.delete_all()


@router.post("/care-companion/reminders", status_code=201)
def create_care_reminder(
    payload: ReminderRequest,
    user: CurrentUser,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    session: Session = Depends(get_session),
):
    if not payload.consent:
        raise HTTPException(
            status_code=403,
            detail={"code": "consent_required", "message": "Reminder consent is required"},
        )
    try:
        ZoneInfo(payload.timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_timezone", "message": "Use a valid IANA timezone"},
        ) from exc
    scheduled = payload.scheduled_at
    if scheduled.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "timezone_required", "message": "Deadline must include a timezone"},
        )
    scheduled = scheduled.astimezone(UTC)
    if scheduled <= datetime.now(UTC):
        raise HTTPException(
            status_code=422,
            detail={"code": "deadline_in_past", "message": "Deadline must be in the future"},
        )
    prior = session.exec(
        select(CareReminder).where(
            CareReminder.user_id == user.id, CareReminder.idempotency_key == idempotency_key
        )
    ).first()
    if prior:
        submitted = (
            payload.title,
            payload.body,
            payload.reminder_type,
            scheduled,
            payload.timezone_name,
            payload.quiet_start,
            payload.quiet_end,
        )
        stored = (
            prior.title,
            prior.body,
            prior.reminder_type,
            prior.scheduled_at,
            prior.timezone_name,
            prior.quiet_start,
            prior.quiet_end,
        )
        if stored != submitted:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "idempotency_conflict",
                    "message": "This idempotency key was used for another reminder",
                },
            )
        return {**prior.model_dump(mode="json"), "demo": True}
    reminder = CareReminder(
        user_id=user.id,
        title=payload.title,
        body=payload.body,
        reminder_type=payload.reminder_type,
        scheduled_at=scheduled,
        timezone_name=payload.timezone_name,
        quiet_start=payload.quiet_start,
        quiet_end=payload.quiet_end,
        idempotency_key=idempotency_key,
    )
    session.add(reminder)
    session.commit()
    session.refresh(reminder)
    return {**reminder.model_dump(mode="json"), "demo": True}


@router.get("/care-companion/reminders")
def list_care_reminders(user: CurrentUser, session: Session = Depends(get_session)):
    rows = session.exec(
        select(CareReminder)
        .where(CareReminder.user_id == user.id)
        .order_by(CareReminder.scheduled_at.desc())
        .limit(100)
    ).all()
    return {
        "items": [row.model_dump(mode="json") for row in rows],
        "demo": True,
        "closed_browser_notifications": False,
    }


@router.post("/care-companion/reminders/{reminder_id}/acknowledge")
def acknowledge_care_reminder(
    reminder_id: str, user: CurrentUser, session: Session = Depends(get_session)
):
    from uuid import UUID

    try:
        reminder = session.exec(
            select(CareReminder).where(
                CareReminder.id == UUID(reminder_id), CareReminder.user_id == user.id
            )
        ).first()
    except ValueError:
        reminder = None
    if reminder is None:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Reminder not found"}
        )
    reminder.acknowledged_at = datetime.now(UTC)
    session.add(reminder)
    session.commit()
    return {"acknowledged": True}
