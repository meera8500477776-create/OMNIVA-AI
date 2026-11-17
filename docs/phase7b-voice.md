# Phase 7B voice assistant

## Flow

The authenticated Voice Assistant uses the existing Phase 7A `FeatureSession`, `TutorMessage`, Gemini adapter, audit events, and rate limiter. The Prisma adapter accepts a validated PCM WAV upload. The frontend shows the transcript in an editable review field and only submits it when the user selects **Send reviewed transcript**. The route sends that text and prior session messages to the configured Gemini model, then sends Gemini's answer to Timbre and returns the response text plus WAV audio for browser playback.

This is a short-clip REST flow. The Phase 7A repository has provider-independent STT/LLM/TTS interfaces, but no LiveKit room/token or WebRTC transport is implemented. Phase 7B does not create duplicate room infrastructure.

## Local configuration

Copy `backend/.env.example` to the gitignored `backend/.env`. Set `GEMINI_API_KEY` and `GNANI_API_KEY` in that local file. Use the verified defaults for `GNANI_STT_URL`, `GNANI_AUTH_HEADER`, `GNANI_MODEL`, `GNANI_LANGUAGE`, `GNANI_OUTPUT_FORMAT`, `GNANI_TTS_URL`, and `GNANI_TTS_MODEL`; use `GNANI_TTS_VOICE` only when overriding the locale defaults. The default voices are Kaveri (`en-IN`) and Suhana (`te-IN`). Do not put secrets in `.env.example` or commit `backend/.env`.

Use `APP_MODE=real` for the voice routes. They fail closed when Gemini or Gnani is unavailable and never substitute demo output in real mode. `GEMINI_MODEL` remains the existing OMNIVA setting.

## Run locally

From the repository root:

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
pnpm install --offline
pnpm dev --host 127.0.0.1
```

Sign in, open **Voice assistant**, select English or Telugu, consent, and start a session. Grant microphone permission when prompted. Stop speaking, review/edit the transcript, then select **Send reviewed transcript**. The response text is saved in the authenticated session and can be played again in the browser.

Audio uploads must be mono PCM WAV produced by the browser converter, at 8–48 kHz, no longer than 30 seconds, and no larger than 10 MB. Audio is not persisted or logged. Transcript text is persisted as conversation context in `TutorMessage` for that authenticated voice session.

## Automated checks

`backend/tests/features/test_gnani_voice.py` covers the provider request contracts, response parsing, format/duration validation, language-to-voice mapping, and a bounded retry. `qa/browser/tests/voice.spec.ts` covers microphone capture with a fake device, transcript review before submission, one turn submission, WAV playback, and a narrow mobile viewport using mocked APIs. The existing API contract suite includes the transcription and cancellation routes.

Live provider calls and browser playback still need a configured Gemini credential and a successful real-browser run before Phase 7B can be described as live verified.
