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

## Demo behavior

`APP_MODE=demo` is an explicit setting. Feature adapters return `demo=true` and simulated state and make no external provider calls. Real mode currently returns 503 for unavailable provider adapters rather than silently simulating. Seed data with `uv run python -m app.seed`; no demonstration login is created by default. Create the initial administrator with `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` set in the environment, then `uv run python -m app.bootstrap_admin`.

The built-in limiter is process-local for development and single-worker deployments. Use a shared Redis/API gateway rate limiter before running multiple production workers.

## Migrations and tests

`uv run alembic upgrade head`; `uv run pytest`. Tests use an isolated SQLite database and never call external providers. Apply production migrations only through a reviewed deployment process.

## License attribution

The architecture and selected authentication/database patterns were informed by the MIT-licensed FastAPI full-stack template (Copyright (c) 2019 Sebastián Ramírez). No substantial template source was copied. If future changes copy template code, include its full MIT license notice in the distribution.
