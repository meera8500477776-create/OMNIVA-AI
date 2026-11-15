from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from app.core.security import decode_access_token
from app.db.models import AuthSession, RoleName, User, UserRole
from app.db.session import get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: SessionDep, token: Annotated[str | None, Depends(oauth2_scheme)]
) -> User:
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id, session_id = decode_access_token(token)
    except jwt.InvalidTokenError, ValueError, KeyError:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_token", "message": "Invalid authentication token"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    auth_session = session.get(AuthSession, session_id)
    user = session.get(User, user_id)
    if (
        auth_session is None
        or auth_session.user_id != user_id
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= datetime.now(UTC)
    ):
        raise HTTPException(
            status_code=401,
            detail={"code": "session_expired", "message": "Session is invalid or expired"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401, detail={"code": "inactive_user", "message": "Account is unavailable"}
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: RoleName):
    def dependency(user: CurrentUser, session: SessionDep) -> User:
        assigned = set(session.exec(select(UserRole.role).where(UserRole.user_id == user.id)).all())
        if not assigned.intersection(roles):
            raise HTTPException(
                status_code=403, detail={"code": "forbidden", "message": "Insufficient permissions"}
            )
        return user

    return dependency
