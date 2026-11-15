# Risk register — Phase 5A

Scores are qualitative: likelihood (L/M/H) × impact (M/H/C). Owners are roles to assign in Phase 5B. No risk is closed by this planning document.

| ID | Risk | L×I | Evidence / impact | Mitigation and exit condition | Owner |
|---|---|---|---|---|---|
| R1 | Missing Phase 2A/3A/4A handoffs | H×H | Only Phase 1 local output found; feature source/contracts cannot be validated | Retrieve docs/SHAs; review and reconcile before integration | Release lead |
| R2 | App source absent from integration branch | H×C | Assigned branch is Phase 1B scaffold; no API, route tree or adapters | Intake exact branches/SHAs; no merge until source and owner verified | Integration lead |
| R3 | 17 routes are not evidenced | H×H | No route declarations in target or sibling frontend inventory | Confirm canonical route list; implement direct-route E2E for every row | Frontend lead |
| R4 | API/auth contract drift | H×C | Phase 1 schemas are explicitly proposed; no implemented OpenAPI | Ratify auth, DTO, errors, consent, idempotency and generate client | Backend + frontend leads |
| R5 | Feature provider calls make demo costly/nonrepeatable | M×H | Voice/tutor and career upstream dependencies possible | Fake adapters, outbound network denial, fixture-only demo; production mode fails closed | Feature leads |
| R6 | Desktop automation creates safety/privacy risk | M×C | Windows input/screen actions are privileged | Separate local companion; simulator-only CI; explicit capabilities and confirmation | Desktop owner/security |
| R7 | Runtime incompatibility | M×H | Phase 1 says Python 3.14 target; observed host Python 3.12; Node 26 may be outside support matrix | Pin supported versions and lockfiles; build matrix before choosing runtime | DevOps |
| R8 | PostgreSQL/container tooling unavailable in developer environment | M×H | Phase 1 host audit: Docker daemon unavailable and psql absent | Use CI service/container; document local fallback and validate target DB version | DevOps |
| R9 | Dependency/package-manager conflict | M×H | UI references use npm/pnpm; feature ecosystems vary; starter has Vite 8/TS6 | Choose one frontend lockfile and supported toolchain; isolate Python adapter deps | Frontend/backend leads |
| R10 | Account/session vulnerabilities | M×C | Auth model and reset flow not implemented | Threat model, CSRF/session revocation, enumeration-safe reset, rate limits, security tests | Security owner |
| R11 | Migration/data loss on rollback | M×C | No migration or backup plan implemented | Expand/contract, backup restore rehearsal, no automatic destructive downgrade | DBA/DevOps |
| R12 | Unlicensed/incompatible reference code/data enters app | L×H | Phase 1 explicitly bars unlicensed career repo; references have differing licenses | License/SBOM review for every dependency and asset; no unapproved source copy | Release lead |
| R13 | Privacy leakage in logs or retained prompts/audio | M×C | Adapters may handle sensitive data; retention unspecified | Minimize, redact, consent, retention/deletion, audit; privacy sign-off | Security/privacy |
| R14 | Accessibility regressions across dashboard/feature experiences | M×H | No implemented screens or audit results | Automated axe plus keyboard/manual checks and release threshold | QA + frontend |
| R15 | Staging/production config drift or secret exposure | M×C | No deployment workflows or environments exist | Immutable artifact promotion, secret scanning, environment isolation and review | DevOps |
| R16 | False readiness inferred from planning documents | H×H | No tests were run; docs are based on proposed contract and sparse source | Label evidence/proposals; require CI/release evidence before readiness claim | Release lead |

## Immediate release blockers

R1–R4 block Phase 5B integration. R5–R6, R10–R13 block final demo acceptance unless deterministic, privacy-safe and isolated paths are proven. R7–R9 and R15 block reproducible CI/deployment. R16 is controlled by explicit reporting and evidence links.
