# Phase 5B QA infrastructure

Run from the integration worktree after application implementation files have been merged into this worktree.

Requirements: Python 3.14 managed by uv, Node 26.13, pnpm 11.25, npm, Docker Desktop with Linux containers. This worktree currently contains only the QA/docs scaffold. The start script checks for actual backend and frontend manifests and stops with BLOCKED if absent; it will not start missing code.

Local setup: copy qa/.env.test.example to qa/.env.test, run qa/scripts/start.ps1, then qa/scripts/run-all.ps1, and finally qa/scripts/stop.ps1.

The disposable Compose project omniva-phase5b-qa owns its Postgres volume and local Mailpit. stop.ps1 removes only that project's volume and containers; reports/logs remain under ignored work/qa-results/. Test settings use demo mode, a test-only signing key and Mailpit. Never put real credentials in the example file.

The Playwright config requires frontend/package.json and frontend/src/App.tsx before loading tests. Set OMNIVA_FRONTEND_DIR to a read-only source checkout to validate before merge; dependencies must already be installed. Tests use Chromium, fixed session state and Vite demo mode, block external hosts, and retain screenshots/traces/videos on failure.

The 17 direct-route checks match the source router. Email Agent and Care Companion feature modules and standalone panels exist at Phase 4C commit 3847b11. They are not mounted or registered in the implementation worktree, so isolated module tests run separately; integrated browser and API checks are skipped until Phase 6 supplies routes and contracts.

API smoke requires a reachable API, seeded catalog and local demo configuration. It uses unique synthetic users. Existing backend tests cover session expiration/revocation, refresh rotation, reset-token single use, authorization, demo/live separation and migrations. The adapter job runs existing adapter unit tests with demo mode and desktop execution disabled.

Two retained API payload regression tests cover source-confirmed mismatches: registration uses name in the frontend while the backend requires display_name; career sends constraints as an object while the backend declares list[str]. They remain Phase 6 integration blockers. See phase5b-implementation-findings.md.

The GitHub workflow detects whether frontend/backend/adapter source has landed. Missing-source jobs are summarized as skipped, never passed. Once source is merged, it runs frontend lint/type/unit/build, Chromium E2E, backend Ruff/pytest/migrations/API smoke/OpenAPI, adapter tests, secret scanning and dependency audits. JUnit, logs, OpenAPI and Playwright artifacts are retained for 14 days. CI uses no production keys, provider calls, desktop executor or real mail configuration.
