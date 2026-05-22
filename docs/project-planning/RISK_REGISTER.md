# Risk Register

| Risk | Impact | Likelihood | Mitigation |
|---|---:|---:|---|
| Scope creep | High | High | Keep MVP tied to `MVP_SCOPE.md`; defer marketplace, full memory, Git integration, all connectors, and Kubernetes |
| Overbuilding MVP | High | Medium | Build thin vertical slices and avoid production automation before core workflow works |
| Poor UI quality | High | Medium | Use Figma-first design, shadcn/ui, realistic empty/loading/error states, and enterprise SaaS patterns |
| Agent output inconsistency | High | High | Require PydanticAI schemas, prompt versions, validation retries, and stored output contracts |
| LLM cost | Medium | Medium | Track tokens, support agent-wise model mapping, allow lower-cost providers and local model URL |
| API key security | High | Medium | Encrypt keys before storage, mask in UI/API, support rotation, test no raw key leakage |
| Uploaded code safety | High | High | Treat uploaded code as untrusted and do not execute arbitrary uploaded code in MVP |
| Docker complexity | Medium | Medium | Keep Compose services minimal and document ports/env vars clearly |
| Connector complexity | High | Medium | Start with metadata/manual import path and defer broad connector catalog |
| Open-source adoption risk | Medium | Medium | Provide clear README, demo flow, screenshots, good first issues, and stable Docker install |
| Temporal complexity | Medium | Medium | Start with one small BMAD workflow and bounded retries |
| Database design drift | High | Medium | Keep PostgreSQL metadata-only policy and Alembic migration review discipline |
| Secret logging | High | Low | Add logging filters and negative tests for secret exposure |
| Artifact storage mismatch | Medium | Medium | Use storage abstraction from the start; local path for MVP, MinIO/S3 later |
| Human approval bypass | High | Low | Enforce approval checks in backend services, not only frontend UI |
