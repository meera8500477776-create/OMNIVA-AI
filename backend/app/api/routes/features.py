import hashlib
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.adapters.base import ProviderUnavailable
from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.db.models import (
    AuditEvent,
    CareerRecommendation,
    Course,
    Enrollment,
    FeatureSession,
    TutorMessage,
)
from app.schemas.features import (
    AvatarSessionRequest,
    CareerItem,
    CareerRequest,
    CareerResponse,
    DesktopSessionRequest,
    FeatureSessionResponse,
    TutorSessionRequest,
    TutorTurnRequest,
    TutorTurnResponse,
    VoiceSessionRequest,
)
from features.ai_adapters.gemini import GeminiError, GeminiProvider

logger = logging.getLogger("omniva.features")
gemini = GeminiProvider(
    settings.gemini_api_key,
    model=settings.gemini_model,
    timeout=settings.gemini_timeout_seconds,
    max_requests_per_minute=settings.gemini_max_requests_per_minute,
    max_requests_per_day=settings.gemini_max_requests_per_day,
)

router = APIRouter(prefix="/features", tags=["feature adapters"])
DESKTOP_CAPABILITIES = {"open_course", "read_lesson", "summarize_progress"}
AVATAR_IDS = {"omniva-guide", "omniva-tutor"}
DISCLAIMER = "Demonstration guidance only; recommendations are not guarantees and are not based on a validated labor-market model."


def unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "provider_unavailable",
            "message": "This feature provider is not configured",
        },
    )


def provider_error(exc: GeminiError) -> HTTPException:
    logger.info("feature_provider_error code=%s", exc.code)
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    )


def save_session(session, payload: dict) -> FeatureSession:
    is_demo = settings.app_mode == "demo"
    payload = {**payload, "demo": is_demo, "state": "simulated" if is_demo else "active"}
    record = FeatureSession(**payload)
    session.add(record)
    session.flush()
    session.add(
        AuditEvent(
            actor_id=record.user_id,
            action=f"feature.{record.feature}.session",
            resource_type="feature_session",
            resource_id=str(record.id),
        )
    )
    session.commit()
    session.refresh(record)
    return record


def session_payload(feature: str, user_id: UUID, metadata: dict, consent: str | None = None) -> dict:
    return {
        "id": uuid4(),
        "user_id": user_id,
        "feature": feature,
        "consent_version": consent,
        "metadata_json": json.dumps(metadata, separators=(",", ":")),
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }


def session_response(record: FeatureSession, **extra) -> FeatureSessionResponse:
    return FeatureSessionResponse(
        session_id=record.id,
        state=record.state,
        demo=record.demo,
        expires_at=record.expires_at,
        **extra,
    )


@router.post(
    "/career/recommendations",
    response_model=CareerResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def career(
    payload: CareerRequest, current_user: CurrentUser, session: SessionDep
) -> CareerResponse:
    if not payload.consent:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "consent_required",
                "message": "Consent is required to process career profile data",
            },
        )
    interests = [item.strip() for item in payload.interests if item.strip()]
    skills = {skill.strip().casefold() for skill in payload.skills if skill.strip()}
    if not interests:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_interests", "message": "At least one interest is required"},
        )
    if settings.app_mode == "demo":
        interest = interests[0][:80]
        result = CareerResponse(
        recommendations=[
            CareerItem(
                domain=interest,
                role="Learning pathway explorer",
                specialization=f"{interest} foundations",
                match_score=0.5,
                rationale=["This simulated result reflects the first interest supplied."],
                skill_gaps=["Communication", "Problem solving"] if not skills else [],
                roadmap=[
                    "Explore introductory lessons",
                    "Practice a small project",
                    "Review progress with a mentor",
                ],
            )
        ],
        taxonomy_version="demo-taxonomy-1",
        model_version="demo-ruleset-1",
        generated_at=datetime.now(UTC),
        limitations=[
            DISCLAIMER,
            "Scores are fixed demonstration values and should not be interpreted as suitability probabilities.",
        ],
            demo=True,
        )
    else:
        prompt = {
            "education_level": payload.education_level,
            "interests": interests,
            "skills": sorted(skills),
            "constraints": payload.constraints or [],
        }
        try:
            raw = await gemini.generate(
                feature="career_guidance",
                user_id=str(current_user.id),
                system=(
                    "Give concise, illustrative career-learning guidance, not hiring or salary predictions. "
                    "Return JSON with recommendations: 1-4 objects having domain, role, specialization, "
                    "match_score (0-100 as a non-probability fit indicator), rationale (strings), skill_gaps, "
                    "roadmap (3-6 practical steps). Use user constraints."
                ),
                messages=[{"role": "user", "text": json.dumps(prompt)}],
                json_mode=True,
            )
            data = json.loads(raw)
            if not isinstance(data.get("recommendations"), list) or not 1 <= len(data["recommendations"]) <= 4:
                raise ValueError
            result = CareerResponse(
                recommendations=data["recommendations"],
                taxonomy_version="gemini-guidance-v1",
                model_version=settings.gemini_model,
                generated_at=datetime.now(UTC),
                limitations=[DISCLAIMER, "AI-generated suggestions are not probabilities or guarantees."],
                demo=False,
            )
        except GeminiError as exc:
            raise provider_error(exc) from None
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=502,
                detail={"code": "invalid_provider_output", "message": "Career provider returned an invalid response"},
            ) from None
    session.add(
        CareerRecommendation(
            user_id=current_user.id,
            model_version=result.model_version,
            taxonomy_version=result.taxonomy_version,
            result_json=result.model_dump_json(),
        )
    )
    session.add(
        AuditEvent(
            actor_id=current_user.id,
            action="feature.career.recommendation",
            resource_type="career_recommendation",
        )
    )
    session.commit()
    return result


@router.post(
    "/tutor/sessions",
    response_model=FeatureSessionResponse,
    status_code=201,
    dependencies=[Depends(enforce_rate_limit)],
)
def tutor_session(
    payload: TutorSessionRequest, current_user: CurrentUser, session: SessionDep
) -> FeatureSessionResponse:
    if not payload.consent:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "consent_required",
                "message": "Consent is required to start a tutor session",
            },
        )
    if settings.app_mode == "real" and not gemini.configured:
        raise unavailable()
    if payload.course_id:
        course = session.get(Course, payload.course_id)
        enrollment = session.exec(
            select(Enrollment).where(
                Enrollment.user_id == current_user.id, Enrollment.course_id == payload.course_id
            )
        ).first()
        if course is None or enrollment is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "course_not_found", "message": "Course not found or not enrolled"},
            )
    try:
        record = save_session(
            session,
            session_payload(
                "tutor",
                current_user.id,
                {
                    "topic": payload.topic,
                    "course_id": str(payload.course_id) if payload.course_id else None,
                    "duration_minutes": payload.duration_minutes,
                },
                consent="tutor-consent-v1",
            ),
        )
    except ProviderUnavailable:
        raise unavailable() from None
    return session_response(record)


@router.post(
    "/tutor/sessions/{session_id}/turns",
    response_model=TutorTurnResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def tutor_turn(
    session_id: UUID, payload: TutorTurnRequest, current_user: CurrentUser, session: SessionDep
) -> TutorTurnResponse:
    record = session.get(FeatureSession, session_id)
    if record is None or record.user_id != current_user.id or record.feature != "tutor":
        raise HTTPException(
            status_code=404,
            detail={"code": "session_not_found", "message": "Tutor session not found"},
        )
    if not payload.text and not payload.audio_ref:
        raise HTTPException(
            status_code=422,
            detail={"code": "input_required", "message": "Provide text or an audio reference"},
        )
    if payload.audio_ref:
        raise HTTPException(
            status_code=503,
            detail={"code": "speech_input_unavailable", "message": "Tutor speech recognition is not configured in Phase 7A"},
        )
    topic = json.loads(record.metadata_json).get("topic", "your topic")
    question = (payload.text or "your question").strip()
    if record.demo:
        answer = f"[DEMO] Let's explore {topic}. You asked: {question[:200]}. Start by identifying the key idea, then try one example."
    else:
        history = session.exec(
            select(TutorMessage).where(TutorMessage.session_id == record.id).order_by(TutorMessage.created_at)
        ).all()
        messages = [{"role": item.role, "text": item.body} for item in history[-12:]]
        messages.append({"role": "user", "text": question})
        try:
            answer = await gemini.generate(
                feature="tutor",
                user_id=str(current_user.id),
                system=f"You are an encouraging AI tutor teaching {topic}. Explain step by step and ask a useful follow-up question. Never just give a test answer without teaching.",
                messages=messages,
            )
        except GeminiError as exc:
            raise provider_error(exc) from None
    session.add(TutorMessage(session_id=record.id, role="user", body=question[:5000]))
    session.add(TutorMessage(session_id=record.id, role="assistant", body=answer))
    session.add(
        AuditEvent(
            actor_id=current_user.id,
            action="feature.tutor.turn",
            resource_type="feature_session",
            resource_id=str(record.id),
        )
    )
    session.commit()
    return TutorTurnResponse(
        answer=answer,
        speech_ref=None,
        board_events=[{"type": "text", "text": f"Demo whiteboard: {topic}"}],
        demo=record.demo,
    )


@router.post(
    "/voice/sessions",
    response_model=FeatureSessionResponse,
    status_code=201,
    dependencies=[Depends(enforce_rate_limit)],
)
def voice_session(
    payload: VoiceSessionRequest, current_user: CurrentUser, session: SessionDep
) -> FeatureSessionResponse:
    if not payload.consent:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "consent_required",
                "message": "Consent is required to start a voice session",
            },
        )
    if settings.app_mode == "real" and not gemini.configured:
        raise unavailable()
    try:
        record = save_session(
            session,
            session_payload(
                "voice",
                current_user.id,
                {"mode": payload.mode, "locale": payload.locale},
                consent="voice-consent-v1",
            ),
        )
    except ProviderUnavailable:
        raise unavailable() from None
    return session_response(record, transport="local-demo" if record.demo else "text-gemini", token=None)


@router.post(
    "/voice/sessions/{session_id}/turns",
    dependencies=[Depends(enforce_rate_limit)],
)
async def voice_turn(session_id: UUID, payload: TutorTurnRequest, current_user: CurrentUser, session: SessionDep):
    record = session.get(FeatureSession, session_id)
    if record is None or record.user_id != current_user.id or record.feature != "voice":
        raise HTTPException(status_code=404, detail={"code": "session_not_found", "message": "Voice session not found"})
    text = (payload.text or "").strip()
    if not text or payload.audio_ref:
        raise HTTPException(status_code=422, detail={"code": "text_required", "message": "Phase 7A voice supports text turns; live speech is a later phase"})
    metadata = json.loads(record.metadata_json)
    history = session.exec(
        select(TutorMessage).where(TutorMessage.session_id == record.id).order_by(TutorMessage.created_at)
    ).all()
    if record.demo:
        answer = "That’s a good question. Let’s take it one step at a time. What part feels most important to understand first?"
    else:
        try:
            answer = await gemini.generate(
                feature="voice_assistant",
                user_id=str(current_user.id),
                system=f"You are an AI voice assistant for learning. Reply in locale {metadata.get('locale', 'en')}; keep it natural, concise, and clear.",
                messages=[*({"role": item.role, "text": item.body} for item in history[-12:]), {"role": "user", "text": text}],
            )
        except GeminiError as exc:
            raise provider_error(exc) from None
    session.add(TutorMessage(session_id=record.id, role="user", body=text[:5000]))
    session.add(TutorMessage(session_id=record.id, role="assistant", body=answer[:5000]))
    session.add(AuditEvent(actor_id=current_user.id, action="feature.voice.turn", resource_type="feature_session", resource_id=str(record.id)))
    session.commit()
    return {"answer": answer, "demo": record.demo, "audio_ref": None, "mode": "text"}


@router.post(
    "/avatar/sessions",
    response_model=FeatureSessionResponse,
    status_code=201,
    dependencies=[Depends(enforce_rate_limit)],
)
def avatar_session(
    payload: AvatarSessionRequest, current_user: CurrentUser, session: SessionDep
) -> FeatureSessionResponse:
    if not payload.consent:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "consent_required",
                "message": "Consent is required to start an avatar session",
            },
        )
    if payload.avatar_id not in AVATAR_IDS:
        raise HTTPException(
            status_code=422, detail={"code": "unknown_avatar", "message": "Avatar is not available"}
        )
    try:
        record = save_session(
            session,
            session_payload(
                "avatar",
                current_user.id,
                {"avatar_id": payload.avatar_id, "audio_ref_received": True},
                consent="avatar-consent-v1",
            ),
        )
    except ProviderUnavailable:
        raise unavailable() from None
    return session_response(record, playback_url=None)


@router.post(
    "/desktop/sessions",
    response_model=FeatureSessionResponse,
    status_code=201,
    dependencies=[Depends(enforce_rate_limit)],
)
def desktop_session(
    payload: DesktopSessionRequest, current_user: CurrentUser, session: SessionDep
) -> FeatureSessionResponse:
    if not set(payload.capabilities).issubset(DESKTOP_CAPABILITIES):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "unsupported_capability",
                "message": "One or more desktop capabilities are not allowed",
            },
        )
    if settings.app_mode != "demo":
        raise unavailable()
    challenge = secrets.token_urlsafe(24)
    metadata = {
        "capabilities": payload.capabilities,
        "challenge_digest": hashlib.sha256(challenge.encode()).hexdigest(),
    }
    record = save_session(
        session,
        session_payload("desktop", current_user.id, metadata, consent=payload.consent_version),
    )
    return session_response(record, companion_challenge=None)
