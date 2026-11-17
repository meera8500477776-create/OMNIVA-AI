import asyncio
import io
import json
import wave
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from features.ai_adapters import gnani_voice as gnani_module
from features.ai_adapters.gnani_voice import GnaniError, GnaniVoice


def pcm_wav(seconds=1):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 16000 * seconds)
    return output.getvalue()


def provider():
    return GnaniVoice(
        SimpleNamespace(
            gnani_api_key=SecretStr("test-provider-key"),
            gnani_auth_header="X-API-Key-ID",
            gnani_stt_url="https://example.test/stt",
            gnani_model="prisma-v3.0",
            gnani_language="indic-auto",
            gnani_output_format="codemix",
            gnani_timeout_seconds=1,
            gnani_tts_url="https://example.test/tts",
            gnani_tts_model="timbre-v2.5",
            gnani_tts_voice="",
            gnani_tts_timeout_seconds=1,
        )
    )


class FakeResponse:
    def __init__(self, *, status=200, body=None, content_type="audio/wav"):
        self.status_code = status
        self.headers = {"content-type": content_type}
        self.content = pcm_wav() if body is None else body

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            request = httpx.Request("POST", "https://example.test")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("provider response", request=request, response=response)

    def json(self):
        return json.loads(self.content)


class FakeClient:
    responses = []
    calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def patch_client(monkeypatch, responses):
    FakeClient.responses = list(responses)
    FakeClient.calls = []
    monkeypatch.setattr(gnani_module.httpx, "AsyncClient", lambda **kwargs: FakeClient())


def test_wav_duration_and_format_limits():
    GnaniVoice.validate_wav(pcm_wav())
    with pytest.raises(GnaniError, match="30 seconds"):
        GnaniVoice.validate_wav(pcm_wav(31))
    with pytest.raises(GnaniError, match="valid PCM WAV"):
        GnaniVoice.validate_wav(b"not audio")


@pytest.mark.parametrize("locale,expected", [("en", "Kaveri"), ("te", "Suhana")])
def test_language_to_timbre_voice(locale, expected):
    resolved_locale, voice = GnaniVoice.timbre_voice(locale)
    assert resolved_locale == ("te-IN" if locale == "te" else "en-IN")
    assert voice == expected


def test_prisma_uses_verified_multipart_contract_and_parses_transcript(monkeypatch):
    response = FakeResponse(
        body=b'{"data":{"transcript":"Nenu DSA nerchukuntunnanu","detected_language_code":"te"}}',
        content_type="application/json",
    )
    patch_client(monkeypatch, [response])
    result = asyncio.run(provider().transcribe_with_metadata(pcm_wav(), "te"))
    assert result == {"transcript": "Nenu DSA nerchukuntunnanu", "language": "te"}
    url, request = FakeClient.calls[0]
    assert url == "https://example.test/stt"
    assert request["headers"]["X-API-Key-ID"] == "test-provider-key"
    assert request["data"] == {
        "model": "prisma-v3.0",
        "language_code": "indic-auto",
        "format": "codemix",
    }
    assert request["files"]["audio_file"][2] == "audio/wav"


@pytest.mark.parametrize(
    "locale,expected_locale,expected_voice", [("en", "en-IN", "Kaveri"), ("te", "te-IN", "Suhana")]
)
def test_timbre_uses_verified_json_contract(monkeypatch, locale, expected_locale, expected_voice):
    patch_client(monkeypatch, [FakeResponse()])
    result = asyncio.run(provider().synthesize("Hello", locale=locale))
    assert result.startswith(b"RIFF")
    url, request = FakeClient.calls[0]
    assert url == "https://example.test/tts"
    assert request["json"]["model"] == "timbre-v2.5"
    assert request["json"]["language"] == expected_locale
    assert request["json"]["voice"] == expected_voice


def test_provider_rate_limit_gets_one_bounded_retry(monkeypatch):
    patch_client(
        monkeypatch,
        [
            FakeResponse(status=429),
            FakeResponse(body=b'{"transcript":"Hello"}', content_type="application/json"),
        ],
    )
    result = asyncio.run(provider().transcribe_with_metadata(pcm_wav()))
    assert result["transcript"] == "Hello"
    assert len(FakeClient.calls) == 2
