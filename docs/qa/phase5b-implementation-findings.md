# Phase 5B implementation findings

Evidence was read-only from the named source worktrees on 2026-11-15. No implementation worktree was modified. These are contract or safety gaps for Phase 6 owners to resolve.

| ID | Finding | Evidence | QA consequence / owner |
|---|---|---|---|
| I-01 | Frontend registration sends {name,email,password} but backend RegisterRequest expects display_name | frontend/src/lib/auth.tsx; backend/app/schemas/auth.py and /api/v1/auth/register | Live registration returns 422 unless contract is reconciled. Frontend/backend owners; API contract test added. |
| I-02 | Frontend profile PATCH uses {name,email} while backend profile schema uses declared fields; verify display_name vs name | frontend/src/pages-account.tsx; PATCH /api/v1/auth/me | Add request contract test; confirm field names and response mapping before live mode. |
| I-03 | Career UI sends constraints as an object {goal}; backend CareerRequest.constraints is list[str] or None | frontend/src/pages-tools.tsx; backend/app/schemas/features.py | Live career request fails validation. QA contract test added. |
| I-04 | Phase 4C Email Agent and Care Companion modules and feature-owned TSX panels exist at commit 3847b11, but are standalone and not registered | backend/features/email_agent, backend/features/care_companion, frontend/src/features panels, docs/phase4c | Isolated Python tests run separately; integrated API/browser checks remain skipped until Phase 6 routes and contracts exist. |
| I-05 | Feature adapter classes are not registered as API routes in ai-feature-integration; backend owns separate demo endpoint behavior | backend/features/ai_adapters/README.md says adapters are not registered; backend/app/api/routes/features.py | Phase 6 must integrate or intentionally replace adapter implementation and add contract tests. |
| I-06 | Desktop endpoint creates a simulated session but core API has no preview/approve/execute/emergency-stop endpoints | backend/app/api/routes/features.py; AI adapter has local preview/approval methods but no OS executor | E2E checks only simulator behavior. Do not claim desktop execution/approval is integrated. |
| I-07 | Voice UI is a text demo and reports no microphone usage; backend voice endpoint requires consent and returns demo token null | frontend/src/pages-tools.tsx; backend/app/api/routes/features.py | Demo QA asserts no mic/provider call. Live voice transport and consent UX are not connected. |
| I-08 | Password reset UI only exposes forgot-password in route tree; no reset-token entry route exists | frontend/src/App.tsx; backend exposes /auth/password/reset | API tests exercise invalid token misuse; browser reset journey remains unavailable until UI route is added. |
| I-09 | additional-ai-features contains a backend-core snapshot plus Phase 4C feature modules; feature panels are not mounted in the main app | exact commit 3847b11 and docs/phase4c/phase6-integration.md | Merge only feature-owned directories after core conflict review; do not describe Phase 4C features as absent. |

## Current QA scope

The Playwright route list mirrors the frontend source's 17 declared routes. API smoke contracts mirror current FastAPI declarations, not Phase 1 proposal-only endpoints. qa/api/tests/test_frontend_contracts.py deliberately asserts frontend payload shapes against backend behavior; failures are expected until I-01 and I-03 are fixed by owners. The QA branch does not import or edit sibling implementation files.
