# Technical Execution Plan

## Build Order

1. Monorepo setup
2. Docker Compose foundation
3. Backend foundation
4. Database migrations
5. Frontend shell
6. Authentication and admin setup
7. LLM provider settings
8. Project workspace
9. LLM router
10. Agent runtime
11. Worker and Temporal workflows
12. Developer workspace
13. Artifact metadata and versioning
14. Validation/reconciliation
15. Audit logs and system health
16. Release validation

## Detailed Execution Plans

Each domain has a dedicated execution plan with full implementation detail:

| Domain | Detailed Plan |
|---|---|
| Backend | `BACKEND_EXECUTION_PLAN.md` |
| Frontend | `FRONTEND_EXECUTION_PLAN.md` |
| Agent Runtime | `AGENT_EXECUTION_PLAN.md` |
| Database | `DATABASE_EXECUTION_PLAN.md` |
| Docker / Release | `DOCKER_RELEASE_PLAN.md` |

## Task-Level Execution

For step-by-step implementation tasks, see `docs/mvp/CODEX_TASKS.md`.

## Sprint Cadence

For sprint-by-sprint planning with per-track tasks and acceptance criteria, see `SPRINT_PLAN.md`.

## Related Architecture Docs

| Doc | What it covers |
|---|---|
| `PROJECT_PLAN.md` | Product vision, goals, MVP scope, success criteria, execution phases |
| `FEATURE_BREAKDOWN.md` | 10 epics mapped to features |
| `RISK_REGISTER.md` | 15 tracked risks with mitigation |
| `DECISION_LOG.md` | 15 ADRs + resolved/open decisions |
| `ACCEPTANCE_CRITERIA.md` | Pass/fail criteria per module |
| `../mvp/CODEX_TASKS.md` | 24-step task execution plan with prompt mappings |
| `../mvp/MVP_SCOPE.md` | MVP included/excluded, user journeys, final boundary |
