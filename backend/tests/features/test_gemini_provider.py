import asyncio
import json
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from features.ai_adapters.gemini import GeminiError, GeminiProvider


def test_provider_requires_key_without_making_a_request():
    provider = GeminiProvider(None, transport=lambda *_: pytest.fail("transport must not run"))
    with pytest.raises(GeminiError, match="not configured") as raised:
        asyncio.run(
            provider.generate(
                feature="tutor", user_id="user-a", system="teach", messages=[{"role": "user", "text": "Hi"}]
            )
        )
    assert raised.value.code == "provider_unavailable"


def test_provider_sends_key_in_header_only_and_sanitizes_url_failures(caplog):
    observed = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _limit):
            return json.dumps({"candidates": [{"content": {"parts": [{"text": "Hello from Gemini"}]}}]}).encode()

    def fake_urlopen(request, timeout):
        observed["url"] = request.full_url
        observed["headers"] = request.headers
        observed["body"] = json.loads(request.data)
        observed["timeout"] = timeout
        return Response()

    provider = GeminiProvider(SecretStr("local-test-secret"), timeout=2)
    with patch("features.ai_adapters.gemini.urlopen", fake_urlopen):
        answer = asyncio.run(
            provider.generate(
                feature="tutor",
                user_id="user-a",
                system="Be helpful",
                messages=[{"role": "user", "text": "Explain gravity"}],
            )
        )
    assert answer == "Hello from Gemini"
    assert "local-test-secret" not in observed["url"]
    assert "local-test-secret" not in json.dumps(observed["body"])
    assert observed["headers"]["X-goog-api-key"] == "local-test-secret"
    assert observed["timeout"] == 2
    assert "local-test-secret" not in caplog.text


def test_provider_retries_transient_errors_and_enforces_per_user_caps():
    calls = 0

    def flaky(_body, _timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise GeminiError("provider_rate_limited", "retry", 429, retryable=True)
        return "ok"

    provider = GeminiProvider("local-test", transport=flaky, max_requests_per_minute=3)
    def run(user):
        return asyncio.run(
            provider.generate(
                feature="career_guidance", user_id=user, system="guide", messages=[{"role": "user", "text": "x"}]
            )
        )
    assert run("user-a") == "ok"
    assert calls == 2
    assert run("user-a") == "ok"
    with pytest.raises(GeminiError) as raised:
        run("user-a")
    assert raised.value.code == "usage_limit"
    assert run("user-b") == "ok"


def test_provider_rejects_oversized_inputs_before_transport():
    provider = GeminiProvider("local-test", transport=lambda *_: pytest.fail("transport must not run"))
    with pytest.raises(GeminiError) as raised:
        asyncio.run(
            provider.generate(
                feature="voice", user_id="user-a", system="", messages=[{"role": "user", "text": "x" * 20_001}]
            )
        )
    assert raised.value.code == "input_too_large"
