"""Shared, dependency-free contracts for the OMNIVA feature adapters."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class Mode(StrEnum):
    DEMO = "demo"
    LIVE = "live"


class AdapterError(Exception):
    """Safe, serializable adapter error; never includes provider credentials."""

    def __init__(self, code: str, message: str, http_status: int = 503) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status

    def as_error(self, request_id: str) -> dict[str, object]:
        return {"error": {"code": self.code, "message": self.message, "request_id": request_id}}


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    default_mode: Mode = Mode.DEMO
    provider_timeout_seconds: float = 8.0
    real_desktop_approved: bool = False

    @classmethod
    def from_env(cls) -> RuntimeConfig:
        mode_text = os.getenv("OMNIVA_FEATURES_MODE", "demo").lower()
        try:
            mode = Mode(mode_text)
        except ValueError as exc:
            raise ValueError("OMNIVA_FEATURES_MODE must be demo or live") from exc
        try:
            timeout = float(os.getenv("OMNIVA_PROVIDER_TIMEOUT_SECONDS", "8"))
        except ValueError as exc:
            raise ValueError("OMNIVA_PROVIDER_TIMEOUT_SECONDS must be numeric") from exc
        if not 0.05 <= timeout <= 120:
            raise ValueError("provider timeout must be between 0.05 and 120 seconds")
        desktop_approved = os.getenv("OMNIVA_DESKTOP_REAL_EXECUTION_APPROVED", "").lower() == "true"
        return cls(mode, timeout, desktop_approved)


async def run_bounded[T](awaitable: Awaitable[T], timeout_seconds: float, feature: str) -> T:
    """Bound provider latency, propagate caller cancellation, and sanitize failures."""
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
    except TimeoutError as exc:
        raise AdapterError(f"{feature}_timeout", f"{feature} provider timed out", 504) from exc
    except asyncio.CancelledError:
        raise
    except AdapterError:
        raise
    except Exception as exc:
        raise AdapterError(f"{feature}_provider_error", f"{feature} provider failed", 502) from exc
