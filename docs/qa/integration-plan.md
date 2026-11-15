# Integration plan — Phase 5A

**Status:** planning only. Audit date: 2026-11-15. No implementation, tests, merge, or deployment was performed.

## Evidence and scope

The assigned branch `feat/integration-qa-deploy` is clean at `96da8e2` and contains the Phase 1B scaffold. Its README says frontend/backend are not implemented; backend has no application files, and `docs/phase1/` has only a pointer README. The sibling `feat/frontend-auth-lms` worktree has an uncommitted frontend starter with `main.tsx`, Vite, Vitest setup and package manifest, but no `App`, route declarations, API clients or screens are present in its file inventory. The sibling backend and AI integration worktrees contain scaffold documentation only. These sibling trees were read only. Phase 1 architecture, proposed API contracts and dependency matrix were read from the Phase 1 output bundle. Phase 2A, 3A and 4A preparation documents were not located in the available local Codex workspaces; confirm their paths and obtain their handoffs before implementation.

Consequently, the requested 17 route and five adapter audit is a target inventory, not a claim that the routes/adapters currently exist. No actual route/API mismatch can be asserted beyond the absence of implementations. The principal blocker is missing source/handoff evidence, not a verified pair of conflicting implementations.

## Shared architecture and contract baseline

Use one React/TypeScript SPA and one FastAPI service, with PostgreSQL as canonical identity, LMS progress and feature metadata store. Keep feature adapters behind typed boundaries and provider/desktop transport isolation. Proposed API base is `/api/v1`; standard error envelope is `{error:{code,message,request_id}}`; auth and user-owned resources are server-scoped; all public schemas should be generated from FastAPI OpenAPI and contract-tested. Provider secrets stay server-side. Desktop actions require a separately installed, user-initiated local companion with capability-scoped consent and confirmation for high-impact actions.

The Phase 1 proposal identifies the five adapters as career recommendations, tutor/whiteboard, realtime voice, browser avatar and desktop companion. It proposes auth, courses, progress, health and these adapter endpoints; details live in the Phase 1 API proposal. These are proposals and must be reconciled with the missing Phase 2A–4A handoffs before freezing.

## Cross-team dependencies and blockers

| Dependency | Required decision/artifact | Current status |
|---|---|---|
| Phase 2A/3A/4A handoffs | Exact workspace locations; route list, API schemas, adapter status, tests, known risks | Not located |
| Frontend → backend | API base/version, auth transport, error schema, DTOs, CORS, OpenAPI client | Frontend has no API client or route tree in inspected worktree |
| Auth → all features | Stable user ID, role policy, session refresh/logout, consent record | Proposed only |
| LMS → dashboards | Course/progress canonical entities, pagination, completion/idempotency rules | Proposed only |
| Five adapters → core | Per-adapter DTOs, timeouts, quotas, failure mapping, mock provider seam | No adapter source found |
| Desktop companion | Local installation, handshake, capabilities, audit record and user confirmation | No implementation; deployment isolation required |
| Runtime | Python version, lockfiles, Postgres baseline, container build | Backend manifest absent; Phase 1 notes Python 3.14 target for FastAPI template |

### Contract reconciliation gate

Before any merge, capture each branch's route declarations and OpenAPI schema. Agree one auth model (HttpOnly secure cookie with CSRF or bearer access plus revocable refresh); do not allow UI-local mock auth to masquerade as production identity. Agree request/response schemas, field casing, optionality, status/error mapping, pagination, timestamps/timezones, IDs and idempotency. For each adapter, specify consent, mode, deterministic mock fixture, timeout, provider-disabled behavior and data retention. Generate typed frontend clients from the chosen OpenAPI snapshot and fail CI on unreviewed schema drift.

## Integration sequence

1. **Handoff intake:** retrieve and review Phase 2A/3A/4A docs; identify exact commit SHAs and branch cleanliness; establish feature names and the 17 canonical route paths.
2. **Contract freeze:** reconcile Phase 1 proposals against implementation; publish OpenAPI and TypeScript DTO baseline, auth/consent/error conventions and five adapter schemas.
3. **Backend core:** integrate health/config, database/migrations, auth/session, roles, LMS/course/progress, audit and rate-limit primitives. Add deterministic dependency injection for adapters.
4. **Frontend shell/auth/LMS:** integrate one router and shell, then registration/login/forgot/reset, role-aware dashboards, courses/progress and account/privacy views against local API.
5. **Adapter vertical slices, one at a time:** career (deterministic/local), tutor, avatar (browser-only), voice transport, desktop companion (local isolation last). For each: schema → mock/unit/API tests → integration → UI → security review. Do not gate core demo on external credentials.
6. **Full integration:** merge completed feature branches in a controlled order; run contract, migration, integration and browser suites on the resulting candidate.
7. **Release candidate:** deploy to staging, migrate an empty and upgrade database, exercise deterministic demo, accessibility/security checks, backup/restore rehearsal and rollback runbook.

## Branch merge, conflicts and rollback

Keep `main` protected; work only on `feat/integration-qa-deploy` for these documents. Phase 5B should merge small feature PRs into an integration branch via reviewed PRs in this order: backend contract/core; frontend auth/LMS; adapters individually; deployment. Require clean branch, current base, CI, owner review and explicit conflict resolution. Never force-push shared branches or resolve by silently choosing “ours/theirs”. For conflicts in OpenAPI, migrations, router, package manifests or lockfiles: pause, compare semantic intent with both owners, produce one canonical resolution, regenerate artifacts/lockfile with the pinned tool, and add regression/contract coverage. Keep merge commits or squash per repository policy consistently; record source SHA and resulting integration SHA.

Rollback is a forward operational procedure: stop promotion, redeploy last known good immutable image, restore compatible config, and use backward-compatible expand/contract migrations. Never automatically downgrade a database after writes. Feature flags disable adapters independently; schema changes require backup and tested restore. Preserve audit logs and make rollback decision owner/timestamp visible. For destructive migration, require a tested restore point and explicit release approval.

## Phase 5A exit decision

The seven planning deliverables define proposed integration and QA gates. Readiness for Phase 5B is **conditional**: start only after missing handoffs are retrieved, a 17-route inventory is confirmed, API/auth contracts are ratified, and branch/source SHAs are known. The assigned branch currently has no integrated application to qualify.
