# AI feature adapters

These modules are feature-owned boundaries only. They are not registered as FastAPI routes and do not modify the app scaffold. Route names are the Phase 1 paths in contracts.py. An application integration can map authenticated request bodies into adapter methods and serialize their dictionaries.

Runtime behavior:
- Default mode is demo (OMNIVA_FEATURES_MODE=demo); timeout is OMNIVA_PROVIDER_TIMEOUT_SECONDS=8.
- Live calls require provider objects injected by a trusted integration. No adapter constructs a network client or reads provider credentials.
- Real desktop actions additionally require OMNIVA_DESKTOP_REAL_EXECUTION_APPROVED=true, an injected local companion executor, and approval for the exact preview plan hash. This repo provides no OS executor.
- Career data is original illustrative taxonomy in career.py. Scores are heuristic indicators; no outcome validation is claimed.
- Tutor demo lessons and browser avatar demo events are deterministic and do not call providers.

Tests:
- Python: set PYTHONPATH=backend and run python -m unittest discover -s backend/tests/features -v.
- Avatar browser adapter: node --experimental-strip-types --test frontend/tests/avatar.test.mjs (Node 26+). The source is TypeScript; use the application toolchain for production type-checking.
