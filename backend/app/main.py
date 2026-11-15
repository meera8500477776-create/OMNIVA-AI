import asyncio
import logging
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.deps import get_current_user
from app.api.routes import auth, dashboard, features, health, learning, phase4_features, users
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.db.models import CareReminder
from app.db.session import Session, engine
from features.autopilot.router import create_autopilot_router
from features.autopilot.service import AutopilotService

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("omniva.api")
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)


async def reminder_scheduler() -> None:
    """Persistently dispatch due reminder events; clients receive them by polling."""
    while True:
        try:
            now = datetime.now(UTC)
            with Session(engine) as session:
                due = session.exec(
                    select(CareReminder)
                    .where(CareReminder.status == "scheduled", CareReminder.scheduled_at <= now)
                    .with_for_update(skip_locked=True)
                ).all()
                for reminder in due:
                    local = now.astimezone(ZoneInfo(reminder.timezone_name))
                    start = time.fromisoformat(reminder.quiet_start)
                    end = time.fromisoformat(reminder.quiet_end)
                    in_quiet = (
                        (local.time() >= start or local.time() < end)
                        if start > end
                        else (start <= local.time() < end)
                    )
                    if in_quiet:
                        next_day = local.date() + (
                            timedelta(days=1) if local.time() >= start else timedelta()
                        )
                        reminder.scheduled_at = datetime.combine(
                            next_day, end, ZoneInfo(reminder.timezone_name)
                        ).astimezone(UTC)
                    else:
                        reminder.status = "fired"
                        reminder.fired_at = now
                    session.add(reminder)
                if due:
                    session.commit()
        except Exception:
            logger.exception("Reminder scheduler iteration failed")
        await asyncio.sleep(15)


@app.on_event("startup")
async def start_reminder_scheduler() -> None:
    app.state.reminder_scheduler_task = asyncio.create_task(reminder_scheduler())


@app.on_event("shutdown")
async def stop_reminder_scheduler() -> None:
    task = getattr(app.state, "reminder_scheduler_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


autopilot_service = AutopilotService()


def require_demo_mode() -> None:
    if settings.app_mode != "demo":
        raise HTTPException(
            status_code=503,
            detail={"code": "provider_unavailable", "message": "Live provider is not configured"},
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def security_and_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    content_length = request.headers.get("content-length")
    if (
        content_length
        and content_length.isdigit()
        and int(content_length) > settings.max_request_bytes
    ):
        response = JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "request_too_large",
                    "message": "Request body is too large",
                    "request_id": request_id,
                }
            },
        )
    else:
        response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = (
        "no-store" if request.url.path.startswith("/api/") else "no-cache"
    )
    return response


def error_body(code: str, message: str, request_id: str, **extra) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id, **extra}}


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    detail = (
        exc.detail
        if isinstance(exc.detail, dict)
        else {"code": "http_error", "message": str(exc.detail)}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {**detail, "request_id": getattr(request.state, "request_id", "")}},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    fields = [
        {
            "field": ".".join(str(part) for part in error["loc"] if part != "body"),
            "code": error["type"],
            "message": error["msg"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "request_id": getattr(request.state, "request_id", ""),
                "fields": fields,
            }
        },
    )


@app.exception_handler(IntegrityError)
async def conflict_error(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content=error_body(
            "conflict",
            "The request conflicts with existing data",
            getattr(request.state, "request_id", ""),
        ),
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.exception(
        "Unhandled API error request_id=%s", getattr(request.state, "request_id", ""), exc_info=exc
    )
    return JSONResponse(
        status_code=500,
        content=error_body(
            "internal_error",
            "An unexpected error occurred",
            getattr(request.state, "request_id", ""),
        ),
    )


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "docs": "/docs" if settings.app_env != "production" else "disabled",
    }


app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(learning.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(features.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(phase4_features.router, prefix="/api/v1")
app.include_router(
    create_autopilot_router(autopilot_service, get_current_user),
    prefix="/api/v1",
    dependencies=[Depends(enforce_rate_limit), Depends(require_demo_mode)],
)
