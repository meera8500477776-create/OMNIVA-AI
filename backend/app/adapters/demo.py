from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.config import settings


def require_demo() -> None:
    if settings.app_mode != "demo":
        from app.adapters.base import ProviderUnavailable

        raise ProviderUnavailable("No real provider adapter is configured")


def session_payload(
    feature: str, user_id: UUID, metadata: dict, consent: str | None = None
) -> dict:
    require_demo()
    return {
        "session_id": uuid4(),
        "user_id": user_id,
        "feature": feature,
        "state": "simulated",
        "demo": True,
        "consent_version": consent,
        "metadata_json": __import__("json").dumps(metadata, separators=(",", ":")),
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }
