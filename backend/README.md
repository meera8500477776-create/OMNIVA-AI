# OMNIVA backend

FastAPI shared API service for identity, learning records, dashboard analytics and AI feature adapters. Python 3.14, SQLModel, PostgreSQL and Alembic.

## Local setup

```powershell
uv sync --extra test
Copy-Item ..\.env.example .env
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Set a fresh `SECRET_KEY`, `DATABASE_URL`, `APP_ENV`, `CORS_ORIGINS`, and `APP_MODE=demo` in local environment. Never commit `.env`. Run disposable PostgreSQL locally with Docker Compose using `docker compose -f docker-compose.yml up -d db`.

## Gemini live mode (Phase 7A)

Copy `backend/.env.example` to `backend/.env` and configure `APP_MODE=real` and `GEMINI_API_KEY` locally. Do not paste the key into chat or commit `.env`. `GEMINI_MODEL`, `GEMINI_TIMEOUT_SECONDS`, `GEMINI_MAX_REQUESTS_PER_MINUTE`, and `GEMINI_MAX_REQUESTS_PER_DAY` can be set there; defaults use Gemini 3.5 Flash-Lite, a 15-second timeout, and per-user request caps of 20/minute and 100/day. The adapter sends the key in the `x-goog-api-key` header, limits prompt/output size, retries transient failures, and logs only feature/status metadata.

Tutor, Career Guidance, Voice Assistant text turns, Care Companion conversations, and Autopilot planning use Gemini in real mode. Demo mode remains provider-free and returns labeled simulated results. Voice Assistant remains text-only until STT/TTS integration; Care Companion conversation history is retained within its active process session. AI request caps are process-local and require a shared limiter before multi-worker production deployment.

## Demo behavior

`APP_MODE=demo` is an explicit setting. Feature adapters return `demo=true` and simulated state and make no external provider calls. Real mode requires configured providers and returns typed errors rather than silently simulating. Seed data with `uv run python -m app.seed`; no demonstration login is created by default. Create the initial administrator with `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` set in the environment, then `uv run python -m app.bootstrap_admin`.

The built-in limiter is process-local for development and single-worker deployments. Use a shared Redis/API gateway rate limiter before running multiple production workers.

## Migrations and tests

`uv run alembic upgrade head`; `uv run pytest`. Tests use an isolated SQLite database and never call external providers. Apply production migrations only through a reviewed deployment process.

## License attribution

The architecture and selected authentication/database patterns were informed by the MIT-licensed FastAPI full-stack template (Copyright (c) 2019 Sebastián Ramírez). No substantial template source was copied. If future changes copy template code, include its full MIT license notice in the distribution.
