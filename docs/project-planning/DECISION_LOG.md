# Decision Log

## Architecture Decisions

| ID | Decision | Rationale | Status |
|---|---|---|---|
| ADR-001 | Use FastAPI for backend | Strong Python ecosystem, Pydantic support, OpenAPI docs, agent/runtime fit | Accepted |
| ADR-002 | Use Next.js for frontend | Enterprise app routing, React ecosystem, strong TypeScript support | Accepted |
| ADR-003 | Use PostgreSQL as metadata store | Reliable relational store for tenants, projects, workflows, outputs, audit logs | Accepted |
| ADR-004 | Store metadata, not full production business data by default | Reduces security and compliance risk for self-hosted enterprise users | Accepted |
| ADR-005 | Use Redis | Short-lived cache, lightweight state, rate-limit support | Accepted |
| ADR-006 | Use Temporal OSS | Durable workflows, retries, long-running agent and validation jobs | Accepted |
| ADR-007 | Use LangGraph | Explicit multi-agent orchestration and state transitions | Accepted |
| ADR-008 | Use PydanticAI | Structured LLM outputs and schema validation | Accepted |
| ADR-009 | Use BMAD as methodology | Clear migration planning lifecycle from requirement to validation and sign-off | Accepted |
| ADR-010 | Use Docker Compose for MVP | Simple self-hosted installation and contributor onboarding | Accepted |
| ADR-011 | Use local artifact storage for MVP | Keeps MVP simple while allowing MinIO/S3 later through abstraction | Accepted |
| ADR-012 | Do not execute arbitrary uploaded code in MVP | Uploaded code is untrusted; MVP supports analysis and draft generation only | Accepted |
| ADR-013 | Require human approval for generated artifacts | Prevents overpromising fully automated migration and preserves enterprise control | Accepted |
| ADR-014 | Encrypt and mask API keys | Required for secure bring-your-own-key LLM settings | Accepted |
| ADR-015 | Use separate frontend/backend/worker images | Enables service isolation and future scaling | Accepted |

## Open Decisions

| Topic | Decision needed | Status |
|---|---|---|
| License file | Confirm final license text before public release | ✅ Resolved — Apache 2.0 confirmed in README.md 21 |
| Rate limiting defaults | Define per-user and per-organization defaults | ✅ Resolved — Specified in SECURITY.md (Rate Limiting section) |
| Retention policy | Define default retention for audit logs, reports, and artifacts | ✅ Resolved — Specified in SECURITY.md (Data Retention section) |
| First connectors | Choose first metadata connector after MVP shell | Open — Defer until MVP Phase 4 |
| CI provider | Confirm GitHub Actions workflow shape | Open — CI plan documented in `docs/operations/CI_CD.md`; implementation deferred |
