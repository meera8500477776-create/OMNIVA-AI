"""Bounded Gnani Prisma STT and Timbre TTS adapters."""

from __future__ import annotations

import asyncio
import io
import struct
import wave
from typing import Any

import httpx


class GnaniError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code, self.status = code, status


class GnaniVoice:
    def __init__(self, settings):
        self.settings = settings
        self.key = settings.gnani_api_key.get_secret_value() if settings.gnani_api_key else ""

    @property
    def configured(self) -> bool:
        return bool(self.key.strip())

    @staticmethod
    def timbre_voice(language: str, configured_voice: str = "") -> tuple[str, str]:
        locale = "te-IN" if language in {"te", "te-IN"} else "en-IN"
        return locale, configured_voice or ("Suhana" if locale == "te-IN" else "Kaveri")

    async def _post(
        self, url: str, timeout: float, operation: str, **kwargs: Any
    ) -> httpx.Response:
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, **kwargs)
                if (response.status_code == 429 or response.status_code >= 500) and attempt == 0:
                    await asyncio.sleep(0.2)
                    continue
                response.raise_for_status()
                return response
            except httpx.TimeoutException:
                if attempt == 0:
                    await asyncio.sleep(0.2)
                    continue
                raise GnaniError("provider_timeout", f"Gnani {operation} timed out", 504) from None
            except httpx.HTTPError:
                raise GnaniError("provider_error", f"Gnani {operation} failed", 502) from None
        raise GnaniError("provider_error", f"Gnani {operation} failed", 502)

    @staticmethod
    def validate_wav(data: bytes) -> None:
        if not data or len(data) > 10 * 1024 * 1024:
            raise GnaniError(
                "invalid_audio", "Audio must be non-empty and no larger than 10 MB", 413
            )
        try:
            with wave.open(io.BytesIO(data), "rb") as audio:
                if audio.getcomptype() != "NONE" or audio.getnframes() < 1:
                    raise GnaniError("unsupported_audio", "Upload uncompressed PCM WAV audio", 415)
                if audio.getframerate() < 8000 or audio.getframerate() > 48000:
                    raise GnaniError("unsupported_audio", "WAV sample rate must be 8–48 kHz", 415)
                if audio.getnframes() / audio.getframerate() > 30:
                    raise GnaniError("audio_too_long", "Audio must be 30 seconds or shorter", 413)
        except wave.Error, EOFError, ZeroDivisionError:
            raise GnaniError("unsupported_audio", "Upload a valid PCM WAV recording", 415) from None

    async def transcribe(self, data: bytes, locale: str = "en") -> str:
        result = await self.transcribe_with_metadata(data, locale)
        return result["transcript"] or ""

    async def transcribe_with_metadata(
        self, data: bytes, locale: str = "en"
    ) -> dict[str, str | None]:
        if not self.configured:
            raise GnaniError("provider_unavailable", "Gnani voice provider is not configured", 503)
        self.validate_wav(data)
        headers = {self.settings.gnani_auth_header: self.key}
        form = {
            "model": self.settings.gnani_model,
            "language_code": self.settings.gnani_language,
            "format": self.settings.gnani_output_format,
        }
        try:
            response = await self._post(
                self.settings.gnani_stt_url,
                self.settings.gnani_timeout_seconds,
                "speech recognition",
                headers=headers,
                data=form,
                files={"audio_file": ("recording.wav", data, "audio/wav")},
            )
            payload = response.json()
        except ValueError:
            raise GnaniError("provider_error", "Gnani speech recognition failed", 502) from None
        candidates = [payload]
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            candidates.insert(0, payload["data"])
        for item in candidates:
            if isinstance(item, dict):
                text = item.get("transcript")
                if text is None:
                    text = item.get("text")
                if isinstance(text, str):
                    return {
                        "transcript": text.strip(),
                        "language": item.get("detected_language_code") or item.get("language"),
                    }
        raise GnaniError("invalid_provider_output", "Gnani returned no transcript", 502)

    async def synthesize(self, text: str, voice: str | None = None, locale: str = "en") -> bytes:
        if not self.configured:
            raise GnaniError("provider_unavailable", "Gnani voice provider is not configured", 503)
        if len(text) > 3000:
            raise GnaniError("response_too_long", "Speech response exceeds 3000 characters", 502)
        locale, selected_voice = self.timbre_voice(locale, voice or self.settings.gnani_tts_voice)
        payload = {
            "text": text,
            "voice": selected_voice,
            "model": self.settings.gnani_tts_model,
            "language": locale,
            "speed": 1.0,
            "audio_config": {
                "sample_rate": 48000,
                "num_channels": 1,
                "sample_width": 2,
                "encoding": "linear_pcm",
                "container": "wav",
            },
        }
        response = await self._post(
            self.settings.gnani_tts_url,
            self.settings.gnani_tts_timeout_seconds,
            "speech synthesis",
            headers={self.settings.gnani_auth_header: self.key},
            json=payload,
        )
        content_type = response.headers.get("content-type", "").split(";")[0].lower()
        if content_type not in {
            "audio/wav",
            "audio/x-wav",
            "audio/wave",
            "application/octet-stream",
        }:
            raise GnaniError("invalid_provider_output", "Gnani returned unsupported audio", 502)
        data = response.content
        if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            raise GnaniError("invalid_provider_output", "Gnani returned invalid WAV audio", 502)
        if data[4:8] == b"\xff\xff\xff\xff" or data[40:44] == b"\xff\xff\xff\xff":
            normalized = bytearray(data)
            if normalized[4:8] == b"\xff\xff\xff\xff":
                struct.pack_into("<I", normalized, 4, len(data) - 8)
            if normalized[40:44] == b"\xff\xff\xff\xff":
                struct.pack_into("<I", normalized, 40, len(data) - 44)
            data = bytes(normalized)
        try:
            with wave.open(io.BytesIO(data), "rb") as audio:
                if audio.getnframes() < 1 or audio.getcomptype() != "NONE":
                    raise wave.Error("bad audio")
        except wave.Error, EOFError:
            raise GnaniError(
                "invalid_provider_output", "Gnani returned invalid WAV audio", 502
            ) from None
        return data
