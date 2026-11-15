# Test strategy — Phase 5A

**Status:** strategy only; no tests were executed in this planning phase.

## Test layers and gates

| Layer | Scope | Gate |
|---|---|---|
| Static | TypeScript typecheck, ESLint, Python Ruff/format/type checks, secret scan, dependency/license audit | No errors; high/critical findings triaged and resolved or formally accepted |
| Unit | Validation, auth/session rules, LMS progression, adapter mapping, timeout/retry/error translation, frontend components/hooks | Deterministic; critical business/security branches covered; target ≥80% lines and ≥90% changed critical modules, exclusions documented |
| API | FastAPI endpoint schemas, auth/role/consent, pagination, idempotency, status and error envelopes, OpenAPI snapshot | Every endpoint has positive, invalid, unauthorized and boundary cases |
| Contract | OpenAPI ↔ generated TS client; adapter fixture schemas; frontend consumer expectations | No unexplained schema drift; fixture/contract suite required on every PR |
| Integration | API + PostgreSQL migrations + auth + LMS + injected fake adapters | Isolated DB per run; migrate from empty and prior supported revision; teardown safely |
| Browser E2E | All 17 canonical target routes, core auth, LMS and five feature flows in mock mode | Chromium required; Firefox/WebKit smoke on release candidate where dependencies allow |
| Accessibility | axe plus keyboard and screen-reader-oriented manual checks on auth, dashboards and feature forms | Zero critical/serious automated violations; manual keyboard/focus/labels checks pass |
| Security | SAST, dependency audit, secret scan, DAST on staging, auth/tenant isolation, upload/input limits, CORS/CSRF, rate limits, headers | No open critical/high exploitable findings; security owner sign-off |
| Release | Deterministic demo, smoke, logs/metrics, backup restore and rollback rehearsal | Release acceptance criteria in deployment plan met |

## Scenario coverage

- **Registration:** valid account, duplicate email, normalization, password policy, consent capture, validation, verification flow and throttling.
- **Login/session:** valid/invalid credentials, role routing, expiry/refresh, logout/revocation, CSRF if cookies, no token leakage, locked/throttled state.
- **Forgot/reset:** generic response to prevent account enumeration, mail sink delivery, valid/expired/reused token, password replacement invalidates sessions.
- **LMS:** list/detail, enrollment/authorization, progress save and repeat idempotency, resume position, completion, stale/invalid resource, empty and populated dashboard.
- **Career:** schema bounds, deterministic fixture ranking/explanations/version/disclaimer, consent, no external data/provider calls.
- **Tutor/whiteboard:** create session, text turn, stable board events, invalid state, provider timeout simulation and safe retry policy.
- **Voice:** mock session/token expiry, transcript/error/end event ordering, reconnect, denied consent, no secret in browser/logs; no live provider.
- **Avatar:** seeded audio fixture or generated silent sample, deterministic session and browser rendering fallback; no network/provider.
- **Desktop:** mock companion handshake and allowlisted capability events only; consent revoked, unsupported companion, denial and audit events. Never execute real desktop actions.

## Deterministic demo mode

Use a server-selected `DEMO_MODE` available only in local/CI/staging-demo environments, with startup refusal if enabled in production. Inject fake implementations through the adapter interface; seed fixed users/courses/progress and canned feature outputs by fixture version. Freeze clock/randomness, use fixed UUID fixtures, deterministic ordering and no external network at the adapter boundary. Authentication uses seeded accounts and the same authorization path as normal mode. Forgot-password emails go to a local sink such as Mailpit; never deliver externally. Voice/tutor/avatar outputs are fixtures; desktop companion is a protocol simulator with no OS process/input/screen APIs. CI should assert outbound network is blocked or provider clients are replaced. Demo mode must label simulated data, never accept provider credentials, and fail closed if unknown adapter mode is configured.

## Test data, isolation and reporting

Create an ephemeral PostgreSQL database/container or CI service for DB suites; use migration-managed schema, unique per-run namespace, deterministic fixture seed and cleanup. Never use personal/prod data. Redact emails/tokens/prompts/audio refs in reports. Preserve screenshots, traces, coverage, JUnit and accessibility results as CI artifacts with bounded retention. Flakes are quarantined only with an owner and expiry; retries must not mask a failure. No test run or passing result is claimed by this document.
