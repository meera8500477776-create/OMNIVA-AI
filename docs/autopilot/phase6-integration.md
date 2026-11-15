# Phase 6 integration handoff — Autopilot

This branch contains isolated backend feature modules and a standalone React panel. It does not mount routes, modify shared auth/config/database models, or register a frontend route. Do not merge into the app until these steps are reviewed.

## 1. Module locations and contracts

- Backend: `backend/features/autopilot/` (`contracts.py`, planner, graph, orchestrator, registry, approvals, browser, memory, desktop, cross-feature adapters, service, router).
- Isolated backend tests: `backend/features/autopilot/tests/`.
- Frontend: `frontend/src/features/autopilot/AutopilotDashboard.tsx` and `autopilot.css`.
- Reference audit: `docs/autopilot/source-audit.md`.
- Uses Pydantic v2 already in backend dependencies; no new runtime dependency was added.

## 2. FastAPI and shared authentication

1. Construct `AutopilotService` using reviewed providers/repositories in the shared app lifespan; do not create a second FastAPI app.
2. Mount `create_autopilot_router(service, current_user_dependency=CurrentUser)` under the shared `/api/v1` prefix. This produces `/api/v1/autopilot/...`.
3. Keep the supplied shared auth dependency mandatory. Route handlers derive `user_id` from the authenticated user and scope plan, workflow, approval and memory lookups to it.
4. Preserve the route factory's stable `{code,message}` error shape and add centralized redacted audit middleware/events consistent with `backend/app` conventions.
5. Apply the existing rate limiter and request-size limits to all Autopilot endpoints before enabling live providers.

## 3. PostgreSQL persistence and transaction work

`InMemoryWorkflowRepository` and `InMemoryMemoryRepository` are demo/test implementations only. Implement PostgreSQL repositories using SQLModel and migrations for workflow plans/steps, event sequence, per-step idempotency results, approval records, memory consent, encrypted/approved memory records, retention and audit entries. Add owner foreign keys and composite owner/resource constraints. Persist approval status transitions and one-use consumption atomically (transaction/conditional update) to prevent parallel replay. Use an outbox/worker for delayed reminders and durable progress events. Never persist tokens in memory records or workflow events.

## 4. Planner and tools

The deterministic planner supports one local fictional internship request and a safe summary fallback. For live planning, inject a `PlanningProvider`, validate its Pydantic output, ownership, enum tool names, DAG and minimum risk server-side. Never add shell/Python/JavaScript tools or execute model-authored code. Register one provider implementation at a time with strict timeouts, bounded inputs/outputs, rate limits and sanitized errors. Keep irreversible tool retries disabled.

## 5. Approval and safety integration

Keep dry-run as the default. Preserve action-specific approval IDs, owner/session binding, exact display text/target, immutable plan hash, expiry, single-use consume, denial, cancellation and emergency stop. Move state transitions to durable atomic writes before calling providers. Confirm UI acknowledgement is not sufficient by itself: the server must recheck approval immediately before the call. Any plan change invalidates approvals. Have security review risk classifications before adding tools.

## 6. Browser Use integration

The current browser adapter uses a local fixture in demo and only has an injected provider seam in live; it does not launch a browser. If Browser Use is evaluated, pin/review a version and isolate its worker/browser profile. Disable model-authored Python/JS execution; expose only approved typed tools. Enforce a per-request scheme/domain allowlist, resolve and pin public IPs, reject private/loopback/link-local/reserved ranges, revalidate every redirect, prevent browser subresource/private-network access, and bound downloads/navigation/time/screenshots. Do not use personal accounts in tests. Keep form submission unavailable until the approval and evidence flow is separately implemented.

## 7. Desktop Agent integration

Inject the existing Desktop Agent from `feat/ai-feature-integration` through `DesktopIntegrationAdapter`. Do not import or instantiate another OS automation package. Require the existing local companion/browser confirmation, native approval, allowlisted action, plan hash, emergency stop and audit behavior. Test only its demo mode. Live desktop execution remains unavailable until the companion explicitly reports capability and the user approves the exact action.

## 8. Cross-feature adapters

Inject adapters for Email Agent, Calendar, Career, Tutor, Voice, Desktop, Care Companion and Talking Avatar through `CrossFeatureAdapters`. Missing features return `capability_unavailable`; never imitate a provider result. Email send, external calendar changes and desktop actions must use their own approval gates. Current demo email/calendar actions only return simulation/preview results.

## 9. Frontend and API client

Mount `AutopilotDashboard` as a protected route inside the existing React app. Supply an `AutopilotApi` implementation backed by the shared `frontend/src/lib/api.ts`, including credentials, timeout and error conventions. Import `autopilot.css` after verifying host design tokens. Test route navigation, pending and expired approvals, polling/unmount cleanup, stop/cancel, mobile/keyboard layout, and server error/empty states. The UI has no standalone data source; render only server-returned results.

## 10. Memory, consent, and privacy

Memory is off by default. Persist consent/version/time, user ownership, provenance, retention and deletion audit. Add admin retention/deletion jobs and an export pathway per product policy. Expand sensitive-data filtering only with privacy review; do not store secrets, OAuth credentials, payment data or raw transcripts by default. Partition retrieval in SQL by authenticated owner; add adversarial cross-user tests.

## 11. Environment template and local demo

`docs/autopilot/env.example` contains placeholders only. The demo has no env requirements and uses no network. From the backend directory, after installing the shared Python 3.14 dependencies, run `uv run pytest features/autopilot/tests -q`. Mounting the route is a Phase 6 task; until then the FastAPI app does not expose these paths. No Node dependency was added. The standalone component is compiled/tested after importing it into the frontend workspace.

## 12. Known incompatibilities and unimplemented live capabilities

- In-memory workflow and memory repositories lose data on process restart and are not multi-worker safe.
- No Browser Use engine, remote page service, live LLM, email sender, calendar writer, desktop companion, or push notification service is configured.
- Browser form submit is explicitly unavailable; form filling is a preview only.
- Reminders are fictional previews, not durable scheduled notifications.
- Dify's modified license is not suitable for casual embedding; source was not copied. UFO overlaps the existing desktop agent and was not added.
- React panel is standalone and needs the existing design tokens/API client and route registration.

## 13. Merge order and conflict risks

Integrate after the shared backend and frontend feature branches are agreed. Merge this feature after `feat/backend-core`, `feat/frontend-auth-lms`, `feat/ai-feature-integration`, and `feat/additional-ai-features` are reconciled. The current branch was based on `feat/additional-ai-features`; expect conflicts if shared contracts, Pydantic versions, route prefixes, or feature names changed. Keep Phase 4D files isolated and resolve conflicts in a dedicated integration review; do not overwrite peer changes.

## 14. Rollback strategy

Remove the Autopilot router include and protected frontend route first. Disable provider registrations and scheduled worker tasks. Preserve existing feature data pending retention/export policy; do not run destructive migrations automatically. Roll back additive schema migrations using reviewed migration scripts only after checking for workflow/history data dependencies.

## 15. Phase 6 acceptance checklist

- [ ] Shared authenticated router mounted at `/api/v1/autopilot`; unauthorized and cross-user requests fail.
- [ ] Durable PostgreSQL repositories, migrations, audit rows, idempotency constraints and worker/outbox reviewed.
- [ ] Pydantic contract, graph, minimum-risk policy and provider configuration tested.
- [ ] Approval expiry, plan tampering, replay, denial, cancellation and emergency stop tested concurrently.
- [ ] Browser URL/DNS/redirect/private-network isolation independently security-tested.
- [ ] Existing Desktop Agent delegation verified in demo mode; no duplicate executor.
- [ ] Cross-feature adapters explicitly unavailable or tested with dedicated demo providers.
- [ ] React route/API adapter compiles, lint/tests pass and Playwright smoke covers approval and cancel.
- [ ] No external action happens without action-specific server-side approval.
- [ ] Production retention, memory consent, monitoring, rate limits and rollback reviewed.
