# Phase 4C reference audit

Audit performed 2026-11-15. References were inspected at the exact default-branch commits below. Repositories were treated as design/architecture references; no reference source, model, dataset, or protected asset was copied.

| Repository | URL | Inspected commit | License | Decision |
|---|---|---|---|---|
| MailPilot AI | https://github.com/alexinwebs/mailpilot-ai | 55d79c3ee8589283cc3606020140f5e0cf20c609 | MIT | Compatible concepts only; Node/Fastify/Prisma stack does not fit backend. |
| Email-agent | https://github.com/ayush-s-tomar/Email-agent | d5341517316247c1146d2a12eb14dea13f6627ca | MIT | UI/workflow ideas only; IMAP/password/public-demo pattern rejected for security. |
| EchoDraft | https://github.com/jeetpoptani/EchoDraft | c739ca90fdfc160f895449dac9046e897a5e53fa | No root license found | No code/assets reused. |
| RealChar | https://github.com/Shaunwei/RealChar | bd452d7ab164098d251935276c870ddfc14a9046 | MIT | High-level real-time conversation reference; no source reused. |
| Warashi | https://github.com/inni918/warashi | 8c71103978dbd34b8595af34eefd14c3028655f6 | MIT; separate Live2D asset exclusions | No source or bundled models/assets reused. |
| RayMe | https://github.com/pedropachecog/RayMe | 1c7b98217de79814ec61bf20b7e61bc0204cb496 | Root project license not established; LICENSES.md covers dependencies/models | No source, models, or assets reused. |
| LiveKit Agents | https://github.com/livekit/agents | cbb5770c716c70009969cd7fa88e3c3662222ce9 | Apache-2.0 | Existing app voice architecture is the integration target; no package copied. |

Licenses/commit references should be rechecked at Phase 6 before any dependency or source reuse.
