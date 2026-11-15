"""Secret-safe, bounded Google Gemini REST client shared by live feature adapters."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import SecretStr

logger = logging.getLogger("omniva.gemini")


class GeminiError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 503, *, retryable: bool = False):
        super().__init__(message)
        self.code, self.status_code = code, status_code
        self.retryable = retryable


class GeminiProvider:
    """Small REST adapter with per-user request caps and no prompt/secret logging."""

    MAX_INPUT_CHARS = 20_000
    MAX_OUTPUT_TOKENS = 1_024

    def __init__(
        self,
        api_key: SecretStr | str | None,
        *,
        model: str = "gemini-2.5-flash",
        timeout: float = 15,
        max_requests_per_minute: int = 20,
        max_requests_per_day: int = 100,
        transport: Callable | None = None,
    ):
        self._api_key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", model):
            raise ValueError("GEMINI_MODEL contains unsupported characters")
        self.model = model
        self.timeout = max(0.1, min(float(timeout), 120))
        self.max_requests_per_minute = max(1, max_requests_per_minute)
        self.max_requests_per_day = max(1, max_requests_per_day)
        self._transport = transport or self._request
        self._minute_calls: dict[str, deque[float]] = defaultdict(deque)
        self._daily_calls: dict[tuple[str, str], int] = defaultdict(int)

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def _take_quota(self, user_id: str) -> None:
        now = time.monotonic()
        calls = self._minute_calls[user_id]
        while calls and now - calls[0] >= 60:
            calls.popleft()
        day = datetime.now(UTC).date().isoformat()
        key = (user_id, day)
        if len(calls) >= self.max_requests_per_minute or self._daily_calls[key] >= self.max_requests_per_day:
            logger.info("gemini_request_limited feature_request=true")
            raise GeminiError("usage_limit", "AI request limit reached; try again later", 429)
        calls.append(now)
        self._daily_calls[key] += 1

    async def generate(
        self,
        *,
        feature: str,
        user_id: str,
        system: str,
        messages: list[dict[str, str]],
        json_mode: bool = False,
    ) -> str:
        if not self.configured:
            raise GeminiError("provider_unavailable", "Gemini is not configured", 503)
        if not messages or any(not isinstance(item.get("text"), str) for item in messages):
            raise GeminiError("invalid_input", "AI message input is invalid", 422)
        if sum(len(item["text"]) for item in messages) + len(system) > self.MAX_INPUT_CHARS:
            raise GeminiError("input_too_large", "AI input exceeds the allowed size", 413)
        contents = [
            {"role": "model" if item.get("role") == "assistant" else "user", "parts": [{"text": item["text"]}]}
            for item in messages
        ]
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": self.MAX_OUTPUT_TOKENS,
                **({"responseMimeType": "application/json"} if json_mode else {}),
            },
        }
        delay = 0.2
        for attempt in range(3):
            try:
                self._take_quota(user_id)
                text = await asyncio.wait_for(
                    asyncio.to_thread(self._transport, body, self.timeout), timeout=self.timeout + 0.5
                )
                if not isinstance(text, str) or not text.strip() or len(text) > 32_000:
                    raise GeminiError("invalid_provider_output", "Gemini returned an invalid response", 502)
                logger.info("gemini_request_succeeded feature=%s attempt=%d", feature, attempt + 1)
                return text.strip()
            except GeminiError as exc:
                if exc.code in {"provider_unavailable", "usage_limit"}:
                    raise
                if not exc.retryable or attempt == 2:
                    raise
                logger.info("gemini_request_retry feature=%s attempt=%d", feature, attempt + 1)
            except TimeoutError as exc:
                if attempt == 2:
                    logger.warning("gemini_request_failed feature=%s code=timeout", feature)
                    raise GeminiError("provider_timeout", "Gemini request timed out", 504) from exc
            except Exception as exc:
                if attempt == 2:
                    logger.warning("gemini_request_failed feature=%s code=provider_error", feature)
                    raise GeminiError("provider_error", "Gemini request failed", 502) from exc
            await asyncio.sleep(delay)
            delay *= 2
        raise GeminiError("provider_error", "Gemini request failed", 502)

    def _request(self, body: dict, timeout: float) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        request = Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self._api_key or "",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read(128_000))
        except HTTPError as exc:
            status = exc.code
            # Never copy provider error bodies into logs or client-visible messages.
            if status == 429:
                raise GeminiError("provider_rate_limited", "Gemini request was rate limited", 429, retryable=True) from None
            raise GeminiError("provider_error", "Gemini request was rejected", 502, retryable=status >= 500) from None
        except (URLError, OSError, TimeoutError) as exc:
            raise GeminiError("provider_connection_error", "Gemini connection failed", 502, retryable=True) from exc
        try:
            return "".join(
                part["text"]
                for part in payload["candidates"][0]["content"]["parts"]
                if isinstance(part.get("text"), str)
            )
        except (KeyError, IndexError, TypeError):
            raise GeminiError("invalid_provider_output", "Gemini returned an invalid response", 502) from None
