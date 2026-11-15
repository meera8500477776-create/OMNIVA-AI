# Phase 5B implementation checklist

This checklist is a handoff for implementation. Phase 5A stops here; no item below is started in this branch.

## 0. Intake and governance

- [ ] Obtain Phase 2A, 3A and 4A preparation docs from their owners/workspaces; record source SHAs and unresolved decisions.
- [ ] Inventory source branches, dirty files, owners, licenses and exact commits; do not alter other worktrees.
- [ ] Confirm canonical 17 routes, five adapter names, demo narrative and release owner.
- [ ] Ratify API version, auth/session/CSRF model, shared DTO/error envelope, consent, pagination, idempotency and retention.
- [ ] Choose supported Node/Python/PostgreSQL/Docker matrix and package managers; create lockfiles and reproducible setup instructions.

## 1. Contracts and core

- [ ] Publish reviewed OpenAPI for auth, health, courses/progress and five adapters.
- [ ] Build schema validation and generated TypeScript client; add schema-drift gate.
- [ ] Implement FastAPI app configuration, health/readiness, structured/redacted logging and error envelope.
- [ ] Implement DB models/migrations, role/ownership checks, auth/session lifecycle and reset mail sink support.
- [ ] Implement course/progress APIs with pagination, idempotency and seed fixtures.
- [ ] Define adapter protocol and injection points: timeout, quotas, safe errors, consent, tracing and fake implementations.

## 2. Frontend and feature vertical slices

- [ ] Implement router/shell and all 17 confirmed routes with loading/empty/error/unauthorized states.
- [ ] Implement register, login, forgot/reset, logout and session-expiry behavior against real API contracts.
- [ ] Implement dashboards, course list/detail, progress and profile/settings/privacy.
- [ ] Implement career adapter with independently licensed rules/data, versioned explainable results and disclaimer.
- [ ] Implement tutor/whiteboard adapter and deterministic board event rendering.
- [ ] Implement voice session adapter with scoped short-lived credentials and mock transport.
- [ ] Implement browser avatar using approved assets and fixture playback/fallback.
- [ ] Implement desktop as isolated local companion protocol; capability scope, consent, confirm high-impact actions; no server shell endpoint.
- [ ] For every vertical slice: unit/API/contract/integration/E2E, accessibility, security review and owner sign-off.

## 3. QA and deterministic demo

- [ ] Add unit/API/integration suites, isolated Postgres and migration upgrade tests.
- [ ] Add Playwright suite for every row in `e2e-test-matrix.md`; verify deep-link/reload, auth gates and errors.
- [ ] Add axe and keyboard checks for auth, dashboards, LMS and each feature flow.
- [ ] Implement demo mode with fixed clock/seed/fixtures, seeded synthetic users, mail sink and adapter fakes.
- [ ] Enforce no external provider calls and no real desktop execution in CI/demo; test production startup rejects demo mode.
- [ ] Add coverage thresholds, trace/JUnit artifacts, flake ownership/expiry and accessibility/security gates.

## 4. CI, merge and deploy

- [ ] Add PR workflows, protected branches, pinned actions, dependency/SBOM/license/secret scans.
- [ ] Merge in approved sequence from `integration-plan.md`; resolve conflicts semantically, regenerate clients/locks, retain audit trail.
- [ ] Build immutable frontend/backend artifacts and promote same digests to staging/prod.
- [ ] Configure managed secrets, TLS/CORS/CSP, database access, backups/PITR, monitoring and incident owners.
- [ ] Test empty/upgrade migrations, staging smoke, backup restore and rollback procedure.
- [ ] Gate provider enablement on credentials, budget caps, quotas, consent, privacy/legal and security approvals.

## 5. Final demo acceptance

- [ ] Every confirmed route renders directly and has access/state/error coverage.
- [ ] Registration/login/reset/logout and learner LMS journey pass on seeded data.
- [ ] Five AI features complete deterministic fixture flows without paid APIs.
- [ ] Desktop demo uses simulator only; evidence confirms zero real OS actions.
- [ ] No secrets are exposed; security and accessibility release gates pass.
- [ ] Required CI passes on declared matrix; no unresolved critical/high issues.
- [ ] Staging deployment, health monitoring, migration, restore and rollback are demonstrated.
- [ ] Release lead records exact commit SHA, test evidence, known limitations and go/no-go.

## Exit

Phase 5B is complete only when all required boxes are checked with linked evidence and the release owner explicitly accepts the demo. Planning documents alone do not indicate implementation or test readiness.
