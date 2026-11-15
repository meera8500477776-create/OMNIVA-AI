# Phase 6 integration notes — Phase 4C

This branch adds feature-owned Python modules and standalone TSX panels only. It does not alter FastAPI route registration, shared auth, database models/migrations, React routes, or application shell.

## Email Agent
- Add authenticated `/api/v1/features/email-agent` routes using the existing `CurrentUser`, `SessionDep`, rate limiter, audit events, and typed feature response conventions.
- Persist OAuth state as short-lived, session-bound, one-use server-side state. Configure OAuth redirect URI and only the `gmail.readonly` plus `gmail.compose` scopes. `TokenVault` must encrypt at rest or use a vetted secret manager. Do not expose refresh/access tokens to the browser.
- Implement provider transport with bounded timeouts and map missing credentials/provider failures to stable 503 errors. Add encrypted token storage configuration and a disconnect path.
- Current send method intentionally always denies; add idempotent approved-send only after the user explicitly authorizes each send. Use a durable unique idempotency key and audit result without message bodies. Auto-send is off and should remain off by default.
- Persist inbox cursors, approval records, automation rules, redacted activity, and reminders in reviewed migrations. No deletion/archive/forward scopes are requested.

## Care Companion
- Wrap the existing LiveKit session infrastructure via `STT`, `LLM`, `TTS` and session adapter seams; no duplicate room/token infrastructure. Enforce session ownership, consent, provider timeouts, cancellation, and transcript policy in shared APIs.
- Add in-app incoming/active/declined/ended/missed call persistence, audio permission UI, mic indicators/mute, locale/provider capability handling, transcript controls, and consented memory deletion.
- `Scheduler` is in-memory only and is a pure test seam. Production requires durable scheduler, user timezone/DST handling, notification preferences, rate limiting, and a push service with opt-in and quiet-hour enforcement.
- This release has no Web Push/PWA/desktop notification worker. A closed tab receives nothing; do not advertise otherwise.

## UI/API
Mount `frontend/src/features/email-agent/EmailAgentPanel.tsx` and `frontend/src/features/care-companion/CareCompanionPanel.tsx` within the authenticated app. Replace placeholder buttons with typed API calls and accessible modal/confirmation states. Adapt visual tokens to the host theme. No browser audio/Gmail permission is requested by these components yet.
