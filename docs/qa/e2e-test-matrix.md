# Browser E2E matrix — 17 target routes

The assigned branch currently implements none of these routes. The frontend feature branch has only an entry point in inspected files and no App/router declarations. This is a **provisional 17-route acceptance inventory** derived from Phase 1 UI areas and proposed API contracts, not a verified route map. Phase 2A/3A/4A owners must confirm names and paths before implementation. Each row is a planned Playwright test with mock API mode and direct-route refresh coverage.

| # | Proposed path | Primary checks | Access / service behavior |
|---:|---|---|---|
| 1 | `/` | Landing content, navigation, responsive layout | Public |
| 2 | `/login` | Validation, success/error, redirect intent | Guest; API mock |
| 3 | `/register` | Field validation, duplicate account, consent | Guest; API mock |
| 4 | `/forgot-password` | Generic success state, validation | Guest; local mail sink |
| 5 | `/reset-password` | Valid/expired token states, success | Guest; API mock |
| 6 | `/dashboard` | Summary cards, loading/empty/error, role-aware links | Authenticated |
| 7 | `/courses` | Search/list, empty/error/pagination | Authenticated |
| 8 | `/courses/:courseId` | Detail, enrollment/access, not found | Authenticated |
| 9 | `/progress` | Save/resume/completion | Authenticated |
| 10 | `/features/desktop` | Consent, capabilities, simulator state | Authenticated; simulator only |
| 11 | `/features/voice` | Mock session, transcript/error/end and reconnect | Authenticated; fake transport |
| 12 | `/features/career` | Valid input, deterministic recommendations/disclaimer | Authenticated; local rules fixture |
| 13 | `/features/tutor` | Create session, text prompt, board event rendering | Authenticated; fixture adapter |
| 14 | `/features/avatar` | Avatar selection, fixture playback/fallback | Authenticated; no provider |
| 15 | `/profile` | Profile read/edit, validation | Authenticated, owner-scoped |
| 16 | `/settings` | Session/security settings, logout | Authenticated |
| 17 | `/privacy` | Consent review/revoke, export/delete request states | Authenticated; audited |

## Common assertions for every route

1. Navigate by link and direct URL; reload deep link; verify expected access control and no console/page errors.
2. Exercise loading, success, empty, validation, unauthorized, not-found and recoverable service-error states where applicable.
3. Check responsive viewport, landmarks, accessible name, heading order, keyboard reachability and focus visibility; run axe.
4. Confirm API calls use the versioned base URL and typed request/response fixtures; no secrets or personal data in client logs.
5. For protected routes, test anonymous redirect and authenticated role/ownership enforcement. Verify logout invalidates protected navigation.

## Flow suites

**Auth:** register → local verification fixture → login → dashboard → logout; invalid login; forgot → sink email → reset once → reject reused token. Assert enumeration-safe forgot response and no outbound email.

**LMS:** seeded learner opens dashboard → course list/detail → starts lesson → updates progress twice → verifies idempotent completion and resume state after reload.

**Five features:** each route runs positive fixture, invalid input/consent denied, adapter unavailable and accessible keyboard flow. Desktop suite asserts simulator calls only and fails if a real companion/native control module is loaded. Feature suites run with provider network denied.

## Cross-browser and determinism

Required every PR: Chromium desktop, representative narrow viewport. Release candidate: Firefox and WebKit smoke, plus Windows browser run if supported by CI. Use fixed fixtures, fixed time, seeded account, stable selectors (`getByRole`/labels), no sleeps, and network interception or injected fake transport. Capture traces/screenshots on failure. Do not execute real desktop actions or provider calls.
