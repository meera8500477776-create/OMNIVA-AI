# Phase 4C readiness and limitations

- Email classification, excerpts, and replies are deterministic illustrative heuristics/templates, not a configured LLM. Email content remains untrusted and detected instruction-like text is flagged, never executed.
- OAuth state is a process-local prototype; production must persist nonce consumption and bind it to authenticated session/CSRF protection. Token vault and Gmail HTTP transport are interfaces only. Live Gmail connect, sync, drafts, search, and send are not implemented or tested.
- Email sending intentionally fails closed even when an approval token is issued. Durable approvals, send implementation, duplicate prevention, searchable history, unread counters, and trusted-sender rule storage require Phase 6.
- Companion conversations are deterministic text demos. No microphone capture, STT/TTS synthesis, LiveKit room, WebRTC, provider audio, or browser test is implemented. Telugu response is a fixed text demo.
- In-app call state and check-in scheduler are process-local. Quiet windows are represented by scheduler windows but do not yet apply a user timezone or DST policy. Notifications are in-app contract-only; no push/background execution, closed-tab calls, PWA, or desktop helper.
- Persona labels are role-play styles with explicit AI identification; no real-person voice cloning exists. These features are supportive conversation, not medical or crisis care.
- TSX components are feature-owned and not wired to the app. The selected backend-core base has only a frontend placeholder, so TypeScript/build/browser tests could not run in this worktree.
- No external network calls, live accounts, credentials, paid providers, or peer worktrees were used by the feature tests.
