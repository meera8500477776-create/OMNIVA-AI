from dataclasses import asdict
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
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
