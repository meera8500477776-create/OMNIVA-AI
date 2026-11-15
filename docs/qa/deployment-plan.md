# Deployment plan — Phase 5A

Planning only. No runtime, cloud target or deployment was selected or executed.

## Environments

- **Local:** Vite frontend, FastAPI, isolated PostgreSQL; optional Mailpit. `.env` stays local and ignored. Use demo fakes and synthetic data.
- **CI:** ephemeral PostgreSQL and fake adapters; no provider credentials, no outbound provider calls, desktop simulator only.
- **Staging:** production-like network and identity configuration, synthetic accounts/data, managed secret store, Mailpit or non-delivery email sink until mail approval. Provider routes disabled by default.
- **Production:** HTTPS, least-privilege service identities, managed PostgreSQL, secret manager, backups/PITR, monitored health/readiness, strict CORS, rate limits, audit and data retention controls. Enable provider adapters individually after consent, budget, legal and security reviews.

## Runtime and topology requirements

Deploy frontend static assets behind HTTPS/CDN/reverse proxy and FastAPI API behind TLS termination. Configure SPA history fallback for the 17 routes and `/api/v1` routing without leaking internal service addresses. Keep database private; restrict admin/metrics access. Use health liveness separate from readiness. Readiness should validate database/configuration, not make paid external requests. Store no provider secret in browser bundle. Desktop companion is a separate user-installed local Windows process; do not deploy remote desktop control through the web service.

## Data and migrations

PostgreSQL is canonical for identity, roles, course/progress, consent and audit metadata. Establish a supported major version and encoding/collation. Use forward-only expand/contract migrations for rolling deployment; deploy additive schema first, compatible application second, remove old columns only in later release. Back up and verify restore before destructive migrations. Define retention/deletion/export behavior for prompts, transcripts, audio references and career data before storing them. Object storage is optional and requires explicit retention/access policy.

## Secrets, access and operations

Use distinct service accounts and secret scopes per environment. Rotate `SECRET_KEY` and provider credentials; avoid secrets in `.env.example`, logs, build args or CI artifacts. Apply HTTPS/HSTS, secure cookie policy/CSRF if cookies, CSP, CORS allowlist, request size limits, rate limits, dependency patch cadence and audit retention. Establish owner/on-call, alert thresholds for availability/error/latency, DB saturation, migration status, queue backlog and provider failure. Redact credentials, tokens, raw prompts, audio and PII from logs.

## Release and rollback

1. Verify build SHA, SBOM, scans, migrations and backup/restore point.
2. Deploy to staging, wait for readiness, run smoke checks and full deterministic demo.
3. Promote the same immutable artifact gradually; monitor error budget and health.
4. Roll back application image/config on failed checks. Disable problematic adapter via feature flag. Do not downgrade schema automatically; preserve backward compatibility and use forward fix or restore only under approved recovery procedure.
5. Record release SHA, migration revision, operator, time and outcome.

## Go-live prerequisites

Provider/data processing agreements and budgets, consent UX and retention policy, password reset mail path, production domain/TLS, database backup/PITR restore proof, alert ownership, vulnerability disposition, traffic/quota limits, privacy request procedure, incident/rollback runbook and demo acceptance sign-off remain unverified and must be completed before production.
