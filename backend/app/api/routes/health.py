from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready(session: SessionDep) -> dict[str, str | bool]:
    try:
        session.exec(text("SELECT 1"))
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={"code": "database_unavailable", "message": "Service is not ready"},
        ) from None
    return {"status": "ready", "database": True, "mode": settings.app_mode}
