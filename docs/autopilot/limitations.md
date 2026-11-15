# Autopilot Phase 4D readiness and limitations

- Pydantic planning, risk and graph contracts are implemented, but the demo planner is intentionally deterministic and supports one fixed internship scenario plus a safe summary fallback. No live LLM is configured.
- The orchestration/repository/approval implementations in this phase are process-local. They demonstrate ownership checks, plan integrity, action-specific approval, timeout, retry, cancellation, pause/resume, parallel safe steps and idempotency, but are not production durable, atomic or multi-worker safe until PostgreSQL repositories are implemented.
- Browser demo reads a local fictional fixture and previews form fields. No browser is launched. Live provider is unconfigured; submission is unavailable. Public IP/domain allowlist checks and pinning are exposed as an adapter seam; a future browser must pin each DNS result and revalidate every redirect and subresource to fully prevent SSRF/DNS rebinding.
- Personal memory is disabled by default and has consent, owner scoping, provenance, expiry, edit and delete. Storage is in-memory in this feature test build; secret-pattern screening is a precaution, not a complete sensitive-data classifier.
- Desktop actions delegate only to an injected existing OMNIVA Desktop Agent; no agent is connected in this branch. No real Windows action was performed.
- Cross-feature adapters are injectable and fail unavailable by default. The demo scenario uses fictional internships, illustrative career comparisons, a draft preview, an approved-but-simulated send result, and a reminder preview. It sends no email and creates no calendar event.
- The React panel is independently integrable; it is not mounted into the app. Browser/TypeScript checks depend on the peer frontend toolchain and were run only if explicitly reported by the test run.
- No browser, LLM, email, calendar, desktop, Mem0, Dify, or other external provider call was made.
