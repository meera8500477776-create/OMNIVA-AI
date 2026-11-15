from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlmodel import Session, select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    new_opaque_token,
    token_digest,
    verify_password,
)
from app.db.models import AuditEvent, AuthSession, PasswordReset, RoleName, User, UserRole
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdate,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.schemas.common import Message, TokenResponse, UserPublic
from app.services.email import send_password_reset

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_COOKIE = "omniva_refresh"
DUMMY_PASSWORD_HASH = hash_password(new_opaque_token())


def user_public(user: User, session: Session) -> UserPublic:
    roles = session.exec(select(UserRole.role).where(UserRole.user_id == user.id)).all()
    return UserPublic(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=[role.value for role in roles],
    )


def issue_session(user: User, session: Session) -> tuple[AuthSession, str, str]:
    raw = new_opaque_token()
    auth_session = AuthSession(
        user_id=user.id,
        refresh_hash=token_digest(raw),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
    )
    session.add(auth_session)
    session.flush()
    return auth_session, raw, create_access_token(user.id, auth_session.id)


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        httponly=True,
        secure=settings.cookies_secure,
        samesite="strict",
        max_age=settings.refresh_token_days * 86400,
        path="/api/v1/auth",
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    dependencies=[Depends(enforce_rate_limit)],
)
def register(
    payload: RegisterRequest, response: Response, session: SessionDep, request: Request
) -> TokenResponse:
    email = str(payload.email).strip().lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(
            status_code=409,
            detail={"code": "email_unavailable", "message": "Email is already registered"},
        )
    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    session.flush()
    session.add(UserRole(user_id=user.id, role=RoleName.student))
    _, refresh, access = issue_session(user, session)
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="auth.register",
            resource_type="user",
            resource_id=str(user.id),
            request_id=getattr(request.state, "request_id", None),
        )
    )
    session.commit()
    set_refresh_cookie(response, refresh)
    return TokenResponse(
        access_token=access,
        expires_in=settings.access_token_minutes * 60,
        user=user_public(user, session),
    )


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(enforce_rate_limit)])
def login(
    payload: LoginRequest, response: Response, session: SessionDep, request: Request
) -> TokenResponse:
    email = str(payload.email).strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    valid = verify_password(payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if user is None or not user.is_active or not valid:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_credentials", "message": "Email or password is incorrect"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    _, refresh, access = issue_session(user, session)
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="auth.login",
            resource_type="user",
            resource_id=str(user.id),
            request_id=getattr(request.state, "request_id", None),
        )
    )
    session.commit()
    set_refresh_cookie(response, refresh)
    return TokenResponse(
        access_token=access,
        expires_in=settings.access_token_minutes * 60,
        user=user_public(user, session),
    )


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(enforce_rate_limit)])
def refresh_token(
    request: Request, response: Response, session: SessionDep, payload: RefreshRequest | None = None
) -> TokenResponse:
    raw = (payload.refresh_token if payload else None) or request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_session", "message": "Refresh session is invalid"},
        )
    current = session.exec(
        select(AuthSession).where(AuthSession.refresh_hash == token_digest(raw)).with_for_update()
    ).first()
    now = datetime.now(UTC)
    if current is None or current.revoked_at is not None or current.expires_at <= now:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_session", "message": "Refresh session is invalid"},
        )
    user = session.get(User, current.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_session", "message": "Refresh session is invalid"},
        )
    current.revoked_at = now
    _, rotated, access = issue_session(user, session)
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="auth.refresh",
            resource_type="auth_session",
            resource_id=str(current.id),
            request_id=getattr(request.state, "request_id", None),
        )
    )
    session.commit()
    set_refresh_cookie(response, rotated)
    return TokenResponse(
        access_token=access,
        expires_in=settings.access_token_minutes * 60,
        user=user_public(user, session),
    )


@router.post("/logout", status_code=204)
def logout(
    current_user: CurrentUser, request: Request, response: Response, session: SessionDep
) -> Response:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        refresh_session = session.exec(
            select(AuthSession)
            .where(AuthSession.refresh_hash == token_digest(raw))
            .with_for_update()
        ).first()
        if (
            refresh_session
            and refresh_session.user_id == current_user.id
            and refresh_session.revoked_at is None
        ):
            refresh_session.revoked_at = datetime.now(UTC)
    bearer = request.headers.get("authorization", "")
    if bearer.lower().startswith("bearer "):
        try:
            _, session_id = decode_access_token(bearer.split(" ", 1)[1])
            active = session.get(AuthSession, session_id)
            if active and active.user_id == current_user.id:
                active.revoked_at = datetime.now(UTC)
        except Exception:
            pass
    session.add(
        AuditEvent(
            actor_id=current_user.id,
            action="auth.logout",
            resource_type="user",
            resource_id=str(current_user.id),
            request_id=getattr(request.state, "request_id", None),
        )
    )
    session.commit()
    response.delete_cookie(
        REFRESH_COOKIE,
        path="/api/v1/auth",
        secure=settings.cookies_secure,
        httponly=True,
        samesite="strict",
    )
    response.status_code = 204
    return response


@router.post(
    "/password/forgot",
    response_model=Message,
    status_code=202,
    dependencies=[Depends(enforce_rate_limit)],
)
def forgot_password(
    payload: ForgotPasswordRequest, background: BackgroundTasks, session: SessionDep
) -> Message:
    email = str(payload.email).strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if user and user.is_active:
        now = datetime.now(UTC)
        for previous in session.exec(
            select(PasswordReset)
            .where(PasswordReset.user_id == user.id, PasswordReset.consumed_at.is_(None))
            .with_for_update()
        ).all():
            previous.consumed_at = now
        token = new_opaque_token()
        session.add(
            PasswordReset(
                user_id=user.id,
                token_hash=token_digest(token),
                expires_at=now + timedelta(minutes=settings.reset_token_minutes),
            )
        )
        session.add(
            AuditEvent(
                actor_id=user.id,
                action="auth.password_reset.request",
                resource_type="user",
                resource_id=str(user.id),
            )
        )
        session.commit()
        background.add_task(send_password_reset, user.email, token)
    return Message(message="If the account exists, password reset instructions have been sent.")


@router.post("/password/reset", status_code=204, dependencies=[Depends(enforce_rate_limit)])
def reset_password(
    payload: ResetPasswordRequest, session: SessionDep, request: Request
) -> Response:
    now = datetime.now(UTC)
    reset = session.exec(
        select(PasswordReset)
        .where(PasswordReset.token_hash == token_digest(payload.token))
        .with_for_update()
    ).first()
    if reset is None or reset.consumed_at is not None or reset.expires_at <= now:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_reset_token", "message": "Reset token is invalid or expired"},
        )
    user = session.get(User, reset.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_reset_token", "message": "Reset token is invalid or expired"},
        )
    reset.consumed_at = now
    user.password_hash = hash_password(payload.new_password)
    for auth_session in session.exec(
        select(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .with_for_update()
    ).all():
        auth_session.revoked_at = now
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="auth.password_reset",
            resource_type="user",
            resource_id=str(user.id),
            request_id=getattr(request.state, "request_id", None),
        )
    )
    session.commit()
    return Response(status_code=204)


@router.get("/me", response_model=UserPublic)
def me(current_user: CurrentUser, session: SessionDep) -> UserPublic:
    return user_public(current_user, session)


@router.patch("/me", response_model=UserPublic)
def update_me(payload: ProfileUpdate, current_user: CurrentUser, session: SessionDep) -> UserPublic:
    current_user.display_name = payload.display_name.strip()
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return user_public(current_user, session)
