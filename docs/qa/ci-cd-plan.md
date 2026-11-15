# CI/CD plan — Phase 5A

Planning only. No workflow files are present in the assigned scaffold and no CI run occurred.

## Pull request workflow

1. Checkout with least-privilege token; pin action versions by full SHA and use concurrency cancellation.
2. Detect frontend/backend/doc changes and run relevant jobs plus required integration checks.
3. Frontend: pinned Node LTS selected after compatibility proof, lockfile-only install (`npm ci` if npm is ratified), typecheck, lint, unit, production build, Playwright mock E2E.
4. Backend: pinned project-local Python, locked sync, Ruff, type checks, pytest unit/API, OpenAPI generation/diff, coverage, dependency/SBOM scan.
5. Integration: PostgreSQL service, migrations from empty and supported upgrade fixture, contract checks, API+frontend Playwright against fake adapters.
6. Security: secret scan, SAST, dependency/license review, container scan when images exist; fail on secrets and unaccepted critical/high findings.
7. Upload bounded artifacts: JUnit, coverage, Playwright trace/screenshots, OpenAPI diff, SBOM. Do not include secrets or real user data.

Required branch protections: PR review, all required checks green, no force pushes, no direct main pushes, resolve conversations, signed/verified commits if repository policy supports them. Cache by lockfile hash and tool version; do not cache secrets or mutable virtualenv state.

## Promotion workflow

Tag an immutable build from reviewed main SHA. Build frontend/backend images once, attach provenance and SBOM, scan, then promote the same digests to staging and production. Staging deploy requires DB migration dry-run/backup readiness, health checks, smoke E2E and approval by release owner. Production is manual approval with canary/gradual rollout, error/latency monitoring and documented rollback. Keep deployment credentials in environment-scoped secret store; separate staging/prod identities.

## Workflow separation and triggers

- PR: lint, unit, API, contracts, integration, deterministic E2E, security scans.
- Main: repeat required suites, build immutable artifacts, publish to registry; no automatic production deploy until release gate established.
- Release tag/manual dispatch: staging promotion then guarded production promotion.
- Nightly: broader browser matrix, dependency update scan, migration/restore rehearsal in isolated environment.

## Configuration and unresolved CI decisions

The assigned branch has no application manifests/workflows. Confirm runner OS, Node LTS, Python version and installer after reconciling Phase 1’s Python 3.14 template requirement with availability. Phase 1 dependency audit observed local Python 3.12.10, Node 26.13.0, npm 11.20.0; Docker CLI existed but daemon was unavailable, `psql` and Bun were absent. Treat these as audit-time host observations, not CI guarantees. Prefer Linux containers for service CI; add Windows runner for Windows-specific packaging/companion protocol tests, with all native actions mocked. Set `TZ=UTC`, locale, fixed seeds and provider-offline mode.

No CI secret should contain a paid provider key for required tests. Optional live-provider smoke belongs in a separately approved, budget-capped manual workflow and is outside Phase 5A/demo acceptance.
