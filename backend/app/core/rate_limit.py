from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

# Process-local guardrail. Production multi-worker deployments must add a shared Redis limiter.
_buckets: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def enforce_rate_limit(request: Request) -> None:
    from app.core.config import settings

    now = monotonic()
    ip = request.client.host if request.client else "unknown"
    key = f"{ip}:{request.url.path}"
    with _lock:
        bucket = _buckets[key]
        while bucket and now - bucket[0] >= settings.rate_limit_window_seconds:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "rate_limited", "message": "Too many requests"},
                headers={"Retry-After": str(settings.rate_limit_window_seconds)},
            )
        bucket.append(now)


def reset_rate_limits() -> None:
    with _lock:
        _buckets.clear()
