# Omniva AI frontend

React 19 + TypeScript + Vite SPA. The UI follows the Phase 1 API and security boundaries and the Phase 2A 17-route map.

## Local setup

```sh
cp .env.example .env.local
pnpm install
pnpm dev
```

Vite development defaults to the clearly labeled demo experience. Demo sign-in: `demo@omniva.ai` / `learn123`. Set `VITE_APP_MODE=live` and `VITE_API_BASE_URL=http://localhost:8000/api/v1` to connect to the Phase 1 FastAPI contract. Live mode never falls back to fixture success. The backend remains a separate workstream and must be running for live data/authentication.

## Checks

```sh
pnpm test
pnpm lint
pnpm build
```

## Source/attribution

The page composition, visual system and app-owned components here are original implementation informed by the audited reference at `shadcnstore/shadcn-dashboard-landing-template` (MIT, inspected Phase 1 commit `866423741fa4b62d5e9427603cb2174aedf00f80`) and auth UI reference `shadcndashboard/shadcndashboard` (MIT, inspected commit `a9fecfad7d4cf440769255b6c99f38f8c0671b71`). No third-party component source was copied into this frontend. Retain these MIT notices if future components are copied from either reference. The unavailable `akkshxy1/smart-lms` was not reused.
