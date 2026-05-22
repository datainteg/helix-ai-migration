# Project Plan

## Product Vision

Helix Migration is an open-source, self-hosted enterprise migration command center. It helps teams plan, validate, reconcile, and govern data migrations with typed AI agent workflows, human approvals, metadata management, and Docker-based deployment.

Helix Migration generates draft migration code, notebook structures, validation plans, and reconciliation reports that must be reviewed and approved by humans before production use.

## Goals

- Provide a Docker Compose installable migration planning and validation platform.
- Support enterprise admin setup, RBAC, LLM provider settings, and auditability.
- Store migration metadata in PostgreSQL without storing full production business data by default.
- Provide a basic Developer Execution Layer for safe code analysis, review, draft conversion, and artifact versioning.
- Make agent outputs typed, validated, stored, auditable, and approval-driven.

## Target Users

| User | Needs |
|---|---|
| Enterprise architects | Migration architecture, dependencies, target-state planning |
| Data engineers | Metadata, mapping drafts, validation rules, ETL code review |
| QA and validation teams | Validation plans, reconciliation reports, mismatch summaries |
| Project managers | Progress, risks, approvals, report exports |
| Admins | Users, roles, LLM settings, audit logs, system health |
| DevOps engineers | Docker deployment, worker health, Temporal workflows |
| Open-source contributors | Clear tasks, architecture boundaries, acceptance criteria |

## Product Layers

| Layer | MVP intent |
|---|---|
| UI / Experience Layer | Dashboard, admin, project workspace, developer workspace shell |
| Management Layer | Projects, requirements, BMAD workflow, approvals, reports |
| Developer Execution Layer | Artifact upload, code review draft flow, versioning, diff review |
| Agent Runtime Layer | BMAD planning agents and first developer agents with typed outputs |
| Workflow Orchestration Layer | Temporal OSS for durable workflows and retries |
| Connector Layer | Metadata-only foundation and future connector framework |
| Validation & Reconciliation Layer | Basic validation and reconciliation reports |
| Metadata & Storage Layer | PostgreSQL global metadata store |
| Artifact Storage Layer | Local filesystem for MVP, MinIO/S3-compatible storage later |
| Governance & Audit Layer | Lightweight audit logs and approval history |
| Observability Layer | Basic system health and worker status |
| Template Layer | Static JSON/YAML templates |
| Deployment Layer | Docker Compose; Helm later |

## MVP Scope

Included:

- Docker Compose installation
- Frontend and backend app shells
- PostgreSQL metadata foundation
- Redis and Temporal OSS
- Login and first admin setup
- Admin panel, LLM provider settings, and agent model mapping
- Project list, project creation, and requirement intake
- Basic BMAD agent workflow with stored outputs and approvals
- Basic developer workspace with artifact metadata and versioning
- Code review draft flow without executing uploaded code
- Basic validation/reconciliation report
- Audit logs and system health

Excluded:

- Full marketplace
- Full vector DB memory
- Full Git integration
- Full automatic code migration
- Arbitrary uploaded code execution
- Full notebook runtime
- All connectors
- Full Kubernetes support
- Production deployment automation

## Success Criteria

- A new contributor can run the MVP locally through Docker Compose.
- An admin can create the first account, configure LLM providers, and manage users.
- A user can create a project, enter requirements, and run a BMAD planning workflow.
- Agent outputs are typed, persisted, and approval-gated.
- A developer can upload `.py` or `.sql`, receive code analysis and review summary, view a draft output diff, and approve or reject the generated artifact.
- PostgreSQL stores metadata only; artifact file content is stored outside PostgreSQL.
- API keys are encrypted before storage and masked in all UI/API responses.

## Execution Phases

| Phase | Outcome |
|---|---|
| 1. Foundation | Repo scaffold, Docker Compose, frontend/backend/worker shells |
| 2. Identity and admin | First admin setup, auth, users, roles, org scope |
| 3. LLM settings | Encrypted providers, key rotation, agent model mapping |
| 4. Project workspace | Projects, requirements, metadata foundation |
| 5. Agent workflow | BMAD planning workflow, approvals, stored outputs |
| 6. Developer workspace | Artifact upload metadata, code review, draft conversion, diff, approval |
| 7. Validation/recon | Basic validation rules, recon summary, report export metadata |
| 8. Launch hardening | Audit logs, health checks, docs, release checklist |

## Delivery Strategy

- Build vertical slices that produce visible, testable user journeys.
- Keep source code execution out of MVP.
- Prefer metadata and structured outputs before advanced automation.
- Use mock or fixture data in frontend before API wiring where useful.
- Add tests with each implementation task.
- Stabilize Docker Compose before open-source launch.

## Open-Source Launch Strategy

- Publish clear README, docs, setup guide, and contribution guide.
- Provide `.env.example`, Docker Compose files, and screenshots.
- Tag a first MVP release only after local install validation passes.
- Use GitHub issues for good first tasks across frontend, backend, agents, docs, and tests.
- Publish Docker images:
  - `datainteg/helix-ai-migration-frontend`
  - `datainteg/helix-ai-migration-backend`
  - `datainteg/helix-ai-migration-worker`

## Planning Docs Map

| Planning Doc | Purpose |
|---|---|
| `FEATURE_BREAKDOWN.md` | 10 epics with detailed feature lists |
| `SPRINT_PLAN.md` | 8 sprints with per-track tasks and acceptance criteria |
| `TECHNICAL_EXECUTION_PLAN.md` | Build order (16 steps) and links to detailed execution plans |
| `AGENT_EXECUTION_PLAN.md` | Agent runtime, BMAD workflow, first agents to build |
| `BACKEND_EXECUTION_PLAN.md` | FastAPI structure, routers, services, schemas |
| `FRONTEND_EXECUTION_PLAN.md` | Next.js routes, components, UI quality rules |
| `DATABASE_EXECUTION_PLAN.md` | Table build order, migrations, metadata policy |
| `DOCKER_RELEASE_PLAN.md` | Image build/push, Compose services, release checklist |
| `RISK_REGISTER.md` | 15 tracked risks with mitigation |
| `DECISION_LOG.md` | 15 ADRs + resolved/open decisions |
| `ACCEPTANCE_CRITERIA.md` | Criteria per module (install, admin, LLM, project, agent, dev workspace, validation, security, audit, UI) |
| `RELEASE_CHECKLIST.md` | Pre-release verification across docs, Docker, demo, screenshots, security |

## Related Architecture Docs

| Doc | What it covers |
|---|---|
| `README.md` | Full product vision, architecture, MVP roadmap, tech stack |
| `ARCHITECTURE.md` | Layer-by-layer architecture, deployment, Kubernetes plan |
| `API_DESIGN.md` | Complete API contract (auth, admin, projects, agents, artifacts, validation, recon, governance, observability) |
| `DATABASE_DESIGN.md` | Table groups, relationships, indexes, encryption, audit design |
| `AGENT_WORKFLOW.md` | BMAD agent flow, memory, prompts, retries, structured outputs |
| `SECURITY.md` | Secrets, RBAC, rate limiting, data retention, audit, Docker security |
