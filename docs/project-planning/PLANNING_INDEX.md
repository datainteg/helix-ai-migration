# Planning Docs Index

> See [README.md](../../README.md) for project identity and product vision.

## Navigation

### Strategy & Vision

| File | Purpose |
|---|---|
| `PROJECT_PLAN.md` | Product vision, goals, target users, product layers, MVP scope, success criteria, execution phases, delivery strategy, open-source launch plan |
| `MVP_DELIVERY_PLAN.md` | MVP feature checklist, non-MVP exclusions, module-by-module delivery order with dependencies, demo flow, definition of done |

### Feature Planning

| File | Purpose |
|---|---|
| `FEATURE_BREAKDOWN.md` | 10 epics (Foundation, Auth/Admin, LLM, Project, Agent, Developer Workspace, Validation/Recon, Governance/Audit, Observability, Docker/Release) |
| `ACCEPTANCE_CRITERIA.md` | Detailed pass/fail criteria per module: Install, Admin, LLM, Project, Agent Workflow, Developer Workspace, Validation/Recon, Security, Audit, UI |

### Execution Plans

| File | Purpose |
|---|---|
| `TECHNICAL_EXECUTION_PLAN.md` | Build order (16 steps) with links to detailed execution plans and CODEX_TASKS.md |
| `SPRINT_PLAN.md` | 8 sprints with per-track tasks (Backend, Frontend, Agent, Database, Testing), acceptance criteria per sprint |
| `AGENT_EXECUTION_PLAN.md` | Agent runtime stack, BMAD workflow, LangGraph orchestration, PydanticAI schemas, LLM router, approval workflow, first agents to implement, future agents, related architecture docs |
| `BACKEND_EXECUTION_PLAN.md` | FastAPI structure, config, auth, database, routers (12), services (20), schemas, LLM provider service, artifact service, audit/health, testing, related architecture docs |
| `FRONTEND_EXECUTION_PLAN.md` | Next.js stack, MVP routes (18), layout shells, reusable components (12), MVP pages, state management, mock data approach, API integration, UI quality rules, build order, related architecture docs |
| `DATABASE_EXECUTION_PLAN.md` | Database principle, migration tables (10 steps), table build order, metadata-only policy, artifact metadata, encrypted secrets, audit logs, indexes, Alembic migration plan, related architecture docs |
| `DOCKER_RELEASE_PLAN.md` | Official images, Compose services (7), environment variables, build/push commands, local test flow, scaling, release checklist, related architecture docs |

### Governance

| File | Purpose |
|---|---|
| `RISK_REGISTER.md` | 15 risks with impact/likelihood/mitigation |
| `DECISION_LOG.md` | 15 ADRs (architecture decisions) + 5 open decisions (3 resolved, 2 open) |
| `RELEASE_CHECKLIST.md` | Pre-release verification: docs, repo artifacts, Docker, env, demo, screenshots, security, GitHub release |

---

## Traceability Matrix

| Epic (FEATURE_BREAKDOWN) | Sprint (SPRINT_PLAN) | Acceptance Criteria (ACCEPTANCE_CRITERIA.md) | Execution Plan |
|---|---|---|---|
| 1. Foundation | Sprint 1 | Install Criteria | `TECHNICAL_EXECUTION_PLAN.md`, `DOCKER_RELEASE_PLAN.md` |
| 2. Auth/Admin | Sprint 2 | Admin Criteria, Security Criteria | BACKEND_EXECUTION_PLAN Auth |
| 3. LLM Settings | Sprint 3 | LLM Settings Criteria | BACKEND_EXECUTION_PLAN LLM Provider Service |
| 4. Project Workspace | Sprint 4 | Project Criteria | BACKEND_EXECUTION_PLAN Routers (projects, metadata) |
| 5. Agent Runtime | Sprint 5 | Agent Workflow Criteria | AGENT_EXECUTION_PLAN |
| 6. Developer Workspace | Sprint 6 | Developer Workspace Criteria | BACKEND_EXECUTION_PLAN Artifact Service, FRONTEND_EXECUTION_PLAN Developer Workspace |
| 7. Validation/Recon | Sprint 7 | Validation/Reconciliation Criteria | BACKEND_EXECUTION_PLAN ValidationService, ReconciliationService |
| 8. Governance/Audit | Sprint 7 | Audit Criteria | DATABASE_EXECUTION_PLAN Audit Logs |
| 9. Observability | Sprint 7 | Install Criteria (health) | BACKEND_EXECUTION_PLAN Audit and Health |
| 10. Docker/Release | Sprint 8 | Install Criteria | DOCKER_RELEASE_PLAN, RELEASE_CHECKLIST |

---

## Quick Reference: Architecture Docs

| Domain | Key Doc |
|---|---|
| Product vision & stack | `README.md` |
| Architecture layers | `ARCHITECTURE.md` |
| API contract | `API_DESIGN.md` |
| Database design | `DATABASE_DESIGN.md` |
| Agent workflow | `AGENT_WORKFLOW.md` |
| Security | `SECURITY.md` |
| UI/UX | `UI_UX_GUIDE.md` |
| Docker | `DOCKER_GUIDE.md` |
| Testing | `TESTING.md` |
| Development | `DEVELOPMENT.md` |

---

## File Count

- **12 planning docs** in `docs/project-planning/` (2 removed: MVP_DELIVERY_PLAN.md, EXECUTION_PLAN.md)
- **PLANNING_INDEX.md** (this document)
