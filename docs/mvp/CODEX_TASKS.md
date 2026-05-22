# Codex Task Plan

## Project Identity

| Item | Value |
|---|---|
| Product | Helix Migration |
| Repository | helix-ai-migration |
| Website | helix.datainteg.io |
| Tagline | Open-source AI-powered migration and validation platform. |
| Frontend image | datainteg/helix-ai-migration-frontend |
| Backend image | datainteg/helix-ai-migration-backend |
| Worker image | datainteg/helix-ai-migration-worker |

Use this file to execute Helix Migration MVP implementation in small, safe tasks. Do not skip ahead unless the user asks.

Before every implementation task, review the relevant planning docs:

- `docs/project-planning/PROJECT_PLAN.md`
- `docs/project-planning/FEATURE_BREAKDOWN.md`
- `docs/project-planning/SPRINT_PLAN.md`
- `docs/project-planning/TECHNICAL_EXECUTION_PLAN.md`
- `docs/project-planning/FRONTEND_EXECUTION_PLAN.md`
- `docs/project-planning/BACKEND_EXECUTION_PLAN.md`
- `docs/project-planning/AGENT_EXECUTION_PLAN.md`
- `docs/project-planning/DATABASE_EXECUTION_PLAN.md`
- `docs/project-planning/DOCKER_RELEASE_PLAN.md`
- `docs/project-planning/ACCEPTANCE_CRITERIA.md`
- `docs/project-planning/RELEASE_CHECKLIST.md`
- `docs/mvp/MVP_SCOPE.md`


## Agent Prompt → Task Mapping

Each agent task uses specific prompt templates. Map tasks to prompts before implementation:

| Task | Agent(s) | Prompt Template | Prompt Doc |
|---|---|---|---|
| Task 8 | Agent Runtime (all) | `system/base_agent_system` | `docs/agents/PROMPT_ENGINEERING.md` |
| Task 9 | Business Analyst Agent | `bmad/ba_requirement_analysis` | `docs/agents/PROMPT_ENGINEERING.md` |
| Task 9 | Architect Agent | `bmad/architect_design` | `docs/agents/PROMPT_ENGINEERING.md` |
| Task 14 | Code Analyzer Agent | `developer/code_analyzer` | `docs/agents/PROMPT_ENGINEERING.md` |
| Task 14 | Code Review Agent | `developer/code_review` | `docs/agents/PROMPT_ENGINEERING.md` |
| Task 16 | Code Migration Agent | `developer/code_migration` | `docs/agents/PROMPT_ENGINEERING.md` |
| Task 16 | Notebook Generator Agent | `developer/notebook_generator` | `docs/agents/PROMPT_ENGINEERING.md` |
| Task 18 | QA / Validation Agent | `bmad/qa_validation_plan` | `docs/agents/PROMPT_ENGINEERING.md` |
| Task 18 | Recon Agent | `bmad/recon_plan` | `docs/agents/PROMPT_ENGINEERING.md` |

### Prompt Versioning Rule

Every agent task must store:

- `prompt_template_id` — which template was used
- `prompt_version_id` — which version was active
- `llm_provider_id` — which provider was called
- `llm_model` — which model was used
- `token_usage` — input/output tokens consumed

### Prompt Evaluation Rule

Before wiring any agent prompt to live LLM calls:

1. Create the prompt template in `prompt_templates` table.
2. Create version 1 in `prompt_versions`.
3. Run schema validation with PydanticAI against mock output.
4. Document the prompt version in the task's implementation notes.

## Task-to-Epic Mapping

| Task | Epic (FEATURE_BREAKDOWN.md) | Sprint (SPRINT_PLAN.md) |
|---|---|---|
| Task 0 | — | Preflight |
| Task 1 | Epic 1: Foundation | Sprint 1 |
| Task 2 | Epic 1: Foundation | Sprint 1 |
| Task 3 | Epic 1: Foundation | Sprint 1 |
| Task 4 | Epic 2: Auth/Admin | Sprint 2 |
| Task 5 | Epic 1: Foundation | Sprint 1 |
| Task 6 | Epic 3: LLM Provider Settings | Sprint 3 |
| Task 7 | Epic 4: Project Workspace | Sprint 4 |
| Task 8 | Epic 5: Agent Runtime | Sprint 5 |
| Task 9 | Epic 5: Agent Runtime | Sprint 5 |
| Task 10 | Epic 6: Developer Workspace | Sprint 6 |
| Task 11 | Epic 6: Developer Workspace | Sprint 6 |
| Task 12 | Epic 6: Developer Workspace | Sprint 6 |
| Task 13 | Epic 6: Developer Workspace | Sprint 6 |
| Task 14 | Epic 6: Developer Workspace | Sprint 6 |
| Task 15 | Epic 6: Developer Workspace | Sprint 6 |
| Task 16 | Epic 6: Developer Workspace | Sprint 6 |
| Task 17 | Epic 6: Developer Workspace | Sprint 6 |
| Task 18 | Epic 7: Validation/Reconciliation | Sprint 7 |
| Task 19 | Epic 8: Governance/Audit | Sprint 7 |
| Task 20 | Epic 9: Observability | Sprint 7 |
| Task 21 | Epic 10: Docker/Release | Sprint 8 |
| Task 22 | Epic 10: Docker/Release | Sprint 8 |
| Task 23 | Epic 10: Docker/Release | Sprint 8 |

## Task-to-Acceptance-Criteria Mapping

| Task | Primary Acceptance Criteria Doc Section |
|---|---|
| Task 1 | Install Criteria |
| Task 2 | Install Criteria |
| Task 3 | Install Criteria |
| Task 4 | Admin Criteria, Security Criteria |
| Task 5 | Install Criteria |
| Task 6 | LLM Settings Criteria |
| Task 7 | Project Criteria |
| Task 8 | Agent Workflow Criteria |
| Task 9 | Agent Workflow Criteria |
| Task 10–17 | Developer Workspace Criteria |
| Task 18 | Validation/Reconciliation Criteria |
| Task 19 | Audit Criteria |
| Task 20 | Install Criteria (health) |
| Task 21 | Install Criteria |
| Task 22 | Install Criteria |
| Task 23 | All criteria (full pass) |
## Global Codex Rules

- Keep MVP focused.
- Do not implement unrelated features.
- Do not claim full automatic production migration.
- Do not execute arbitrary uploaded code in MVP.
- Keep PostgreSQL as the metadata store.
- Store artifact files outside PostgreSQL.
- Encrypt and mask API keys and secrets.
- Treat BMAD as the default migration methodology, not the full product identity.
- Use LangGraph for agent orchestration, PydanticAI for structured outputs, and Temporal OSS for durable workflows.
- Every agent output must be typed, validated, stored, and auditable.

## Task 0: Planning Docs Preflight

Goal: Verify implementation work starts from current planning docs and MVP boundaries.

Scope:

- Review project identity.
- Review MVP included/excluded scope.
- Review final build sequence.
- Confirm no task expands into full marketplace, full vector memory, full Git integration, arbitrary code execution, full notebook runtime, all connectors, or full Kubernetes support.

Files to create/change:

- None unless inconsistencies are found in markdown docs.

Do not change:

- Application source code.
- Docker files.
- Runtime folders.

Acceptance criteria:

- Product name is `Helix Migration`.
- Repo name is `helix-ai-migration`.
- Tagline is `Open-source AI-powered migration and validation platform.`
- Docker images match documented names.
- MVP boundaries match `docs/mvp/MVP_SCOPE.md`.

Test command:

```bash
rg -n "Helix Migration|helix-ai-migration|Open-source AI-powered migration and validation platform|datainteg/helix-ai-migration" README.md docs AGENTS.md
```

Next task: Task 1.

## Task 1: Add Docker Compose Foundation

Goal: Define the primary self-hosted local installation topology.

Scope:

- Add `docker-compose.yml`.
- Add `docker-compose.dev.yml` if needed.
- Add `.env.example`.
- Include frontend, backend, worker, PostgreSQL, Redis, Temporal, and Temporal UI.
- Include local artifact storage path for MVP.

Files to create/change:

- `docker-compose.yml`
- `docker-compose.dev.yml`
- `.env.example`
- Docker-related documentation if commands differ from docs.

Do not change:

- Application business logic.
- Helm or Kubernetes files.

Acceptance criteria:

- Compose uses documented service boundaries.
- Official image names are used where image references are needed:
  - `datainteg/helix-ai-migration-frontend`
  - `datainteg/helix-ai-migration-backend`
  - `datainteg/helix-ai-migration-worker`
- PostgreSQL is the metadata store.
- Artifact storage is outside PostgreSQL.

Test command:

```bash
docker compose config
```

Next task: Task 2.

## Task 2: Create Backend Shell

Goal: Create the FastAPI backend foundation.

Scope:

- FastAPI app entrypoint.
- Settings/config loader.
- Router registration.
- Health endpoint.
- Basic test setup.

Files to create/change:

- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/api/health.py`
- `backend/requirements.txt`
- `backend/tests/`

Do not change:

- Agent runtime implementation.
- Database models beyond connection setup.
- Frontend code.

Acceptance criteria:

- Backend starts locally.
- Health endpoint returns healthy status.
- OpenAPI docs are available through FastAPI.

Test command:

```bash
cd backend && pytest
```

Next task: Task 3.

## Task 3: Add Database Foundation

Goal: Add PostgreSQL ORM, sessions, and Alembic migrations.

Scope:

- SQLAlchemy or SQLModel setup.
- Database session management.
- Alembic initialization.
- Base model conventions.
- Initial migration path.

Files to create/change:

- `backend/app/db/`
- `backend/app/models/`
- `backend/alembic/`
- `backend/alembic.ini`

Do not change:

- Frontend behavior.
- Agent workflow behavior.

Acceptance criteria:

- Database session can connect to PostgreSQL.
- Alembic can apply the first migration.
- Schema design follows `docs/project-planning/DATABASE_EXECUTION_PLAN.md`.

Test command:

```bash
cd backend && alembic upgrade head
```

Next task: Task 4.

## Task 4: Add Auth and Admin Foundation

Goal: Add first admin setup, login, organization scope, and RBAC foundation.

Scope:

- Organizations.
- Users.
- Roles and permissions.
- First admin setup.
- Login and current user endpoints.
- JWT handling.
- RBAC dependency foundation.

Files to create/change:

- `backend/app/models/identity.py`
- `backend/app/schemas/identity.py`
- `backend/app/services/identity_service.py`
- `backend/app/services/auth_service.py`
- `backend/app/api/auth.py`
- `backend/app/auth/`
- Alembic migration
- Tests

Do not change:

- LLM provider logic.
- Project APIs.
- Agent runtime.

Acceptance criteria:

- First admin can be created once.
- User can log in.
- Protected endpoints reject missing or invalid tokens.
- Tenant-owned records include organization scope.

Test command:

```bash
cd backend && pytest
```

Next task: Task 5.

## Task 5: Create Frontend Shell

Goal: Create the Next.js application shell for Management and Developer Execution navigation.

Scope:

- Next.js with TypeScript.
- Tailwind CSS.
- shadcn/ui base.
- App layout.
- Login, dashboard, admin, projects, and developer workspace placeholder routes.

Files to create/change:

- `frontend/`

Do not change:

- Backend contracts unless required for shell integration.
- Agent runtime.

Acceptance criteria:

- Frontend runs locally.
- Core placeholder routes render.
- Navigation reflects Management Layer and Developer Execution Layer.

Test command:

```bash
cd frontend && npm run lint
```

Next task: Task 6.

## Task 6: Add LLM Provider Settings

Goal: Add secure bring-your-own-key provider settings and agent model mapping.

Scope:

- Provider models and migrations.
- Encrypted key storage.
- Masked key responses.
- Key rotation.
- Provider test endpoint.
- Agent-wise model mapping.
- Admin UI for LLM settings.
- Audit logs for provider changes.

Files to create/change:

- `backend/app/models/llm.py`
- `backend/app/schemas/llm.py`
- `backend/app/services/llm_provider_service.py`
- `backend/app/services/secret_service.py`
- `backend/app/api/llm_providers.py`
- `frontend/app/admin/llm-settings/`
- `frontend/lib/api/`
- Tests

Do not change:

- Agent workflow execution.
- Connector implementation.

Acceptance criteria:

- API keys are encrypted before storage.
- API responses never return full keys.
- UI displays masked keys only.
- Key rotation writes audit log.
- Agent model mapping can be saved.

Test command:

```bash
cd backend && pytest
cd ../frontend && npm run lint
```

Next task: Task 7.

## Task 7: Add Project Workspace

Goal: Add project, subproject, requirement, and metadata workspace foundation.

Scope:

- Project APIs.
- Subproject APIs.
- Requirement intake.
- Source and target metadata shell.
- Project list and project detail UI.

Files to create/change:

- `backend/app/models/project.py`
- `backend/app/models/metadata.py`
- `backend/app/schemas/project.py`
- `backend/app/api/projects.py`
- `backend/app/api/metadata.py`
- `backend/app/services/project_service.py`
- `frontend/app/projects/`
- `frontend/features/projects/`
- `frontend/features/metadata/`
- Migrations and tests

Do not change:

- Developer workspace.
- Validation execution.
- Agent execution.

Acceptance criteria:

- User can create project and subproject.
- User can add requirement.
- User can view project workspace.
- Project data is organization-scoped.

Test command:

```bash
cd backend && pytest
cd ../frontend && npm run lint
```

Next task: Task 8.

## Task 8: Add Agent Runtime Skeleton

Goal: Add typed agent task lifecycle without overbuilding the full runtime.

Scope:

- Agent definitions.
- Agent tasks.
- Agent outputs.
- Prompt templates and prompt versions.
- PydanticAI output schema foundation.
- LLM router interface.

Related prompts: `system/base_agent_system` — used for all agent system-level instructions. See `docs/agents/PROMPT_ENGINEERING.md`.

Files to create/change:

- `agents/`
- `backend/app/models/agents.py`
- `backend/app/schemas/agents.py`
- `backend/app/services/agent_service.py`
- `backend/app/services/llm_router_service.py`
- `backend/app/api/agents.py`
- Migrations and tests

Do not change:

- Full connector implementation.
- Full vector memory.
- Developer agents beyond schema placeholders if needed.

Acceptance criteria:

- Agent task can be created.
- Typed output can be validated and stored.
- Prompt version and model/provider metadata can be associated with an output.

Test command:

```bash
cd backend && pytest
```

Next task: Task 9.

## Task 9: Add BMAD Workflow Skeleton

Goal: Add the first durable planning workflow using BMAD methodology.

Scope:

- LangGraph flow for first BMAD steps.
- Temporal workflow wrapper.
- Business Analyst Agent.
- Architect Agent.
- Human approval gate.
- Planning-agent stubs only where needed for flow continuity.
- React Flow workflow canvas foundation.

Related prompts: `bmad/ba_requirement_analysis`, `bmad/architect_design`. See `docs/agents/PROMPT_ENGINEERING.md`.

Files to create/change:

- `agents/runtime/`
- `agents/bmad/`
- `worker/workflows/`
- `worker/activities/`
- `backend/app/api/agent_workflows.py`
- `frontend/features/agent-workflow/`
- `frontend/app/projects/[id]/agents/`
- Tests

Do not change:

- Validation engine internals.
- Developer execution agents.

Acceptance criteria:

- Workflow starts from a requirement.
- BA and Architect outputs are typed.
- Human approval gate blocks later steps.
- Workflow state is visible in UI.

Test command:

```bash
cd backend && pytest
cd ../worker && pytest
cd ../frontend && npm run lint
```

Next task: Task 10.

## Task 10: Add Artifact Metadata and Versioning

Goal: Add Developer Workspace metadata models before upload and review flows.

Scope:

- Artifact metadata.
- Artifact versions.
- Content hashes.
- Storage locations.
- Dependencies.
- Lineage.
- Artifact approvals.

Files to create/change:

- `backend/app/models/artifacts.py`
- `backend/app/schemas/artifacts.py`
- `backend/app/services/artifact_version_service.py`
- Alembic migration
- Tests

Do not change:

- File execution behavior.
- Full Git integration.
- MinIO/S3 integration beyond storage abstraction design.

Acceptance criteria:

- Models include organization and project scope.
- Artifact versions include content hash and approval status.
- PostgreSQL stores metadata only.
- Artifact files are stored outside PostgreSQL.

Test command:

```bash
cd backend && pytest
```

Next task: Task 11.

## Task 11: Add Artifact Upload API Metadata Only

Goal: Add safe `.py` and `.sql` upload flow for MVP.

Scope:

- Upload endpoint.
- File type validation.
- Content hash calculation.
- Local filesystem storage abstraction.
- Artifact and first version metadata creation.
- Audit log for upload.

Files to create/change:

- `backend/app/api/artifacts.py`
- `backend/app/services/artifact_service.py`
- `backend/app/storage/`
- Tests

Do not change:

- LLM provider logic.
- Agent workflow execution.
- Do not execute uploaded code.

Acceptance criteria:

- Upload creates artifact and version metadata.
- Unsupported file types are rejected.
- Uploaded code is treated as untrusted input.
- API does not execute uploaded code.

Test command:

```bash
cd backend && pytest
```

Next task: Task 12.

## Task 12: Add Developer Workspace UI Shell

Goal: Add the first Developer Execution Layer workspace experience.

Scope:

- Developer workspace route.
- Project artifact route.
- Code Review Center shell.
- Left artifact explorer.
- Center source/generated/diff area.
- Right AI review panel.
- Bottom logs/version area.

Files to create/change:

- `frontend/app/projects/[id]/developer-workspace/`
- `frontend/app/projects/[id]/artifacts/`
- `frontend/app/projects/[id]/code-review/`
- `frontend/features/developer-workspace/`

Do not change:

- Backend contracts without updating tests.
- Admin pages.
- Validation pages.

Acceptance criteria:

- Routes render empty states.
- Shell matches Developer Workspace layout in `UI_UX_GUIDE.md`.
- Generated outputs are visually marked as draft.

Test command:

```bash
cd frontend && npm run lint
```

Next task: Task 13.

## Task 13: Add Side-by-Side Diff Component Shell

Goal: Display original and generated draft artifacts side by side.

Scope:

- Reusable diff viewer.
- Source content panel.
- Generated draft panel.
- Empty, loading, and error states.
- Approval status display.

Files to create/change:

- `frontend/features/developer-workspace/components/DiffViewer.tsx`
- `frontend/features/developer-workspace/components/CodeEditor.tsx`
- `frontend/features/developer-workspace/components/AIReviewPanel.tsx`

Do not change:

- Conversion service.
- Backend APIs.

Acceptance criteria:

- Component shows original and generated content side by side.
- Draft status is clear.
- Component handles empty/loading/error states.

Test command:

```bash
cd frontend && npm run lint
```

Next task: Task 14.

## Task 14: Add Code Review Agent Schema

Goal: Define typed Developer Execution agent outputs for safe review.

Scope:

- Code Analyzer Agent output schema.
- Code Review Agent output schema.
- Fields for dependencies, inputs, outputs, transformations, risks, quality findings, security findings, performance findings, assumptions, and limitations.

Related prompts: `developer/code_analyzer`, `developer/code_review`. See `docs/agents/PROMPT_ENGINEERING.md`.

Files to create/change:

- `agents/code_analyzer_agent/`
- `agents/code_review_agent/`
- `agents/schemas/`
- `backend/app/schemas/agents.py`
- Tests

Do not change:

- Generated code execution.
- Full code migration implementation.

Acceptance criteria:

- Schemas validate sample outputs.
- Outputs are typed and versioned.
- Findings include security and hardcoded-secret checks.

Test command:

```bash
cd backend && pytest
```

Next task: Task 15.

## Task 15: Add Code Review Draft Flow

Goal: Connect artifact upload metadata to code analysis and review summaries.

Scope:

- Analyze artifact endpoint.
- Review artifact endpoint.
- Code review service.
- Store review summary and comments.
- UI integration for AI Review Panel.

Files to create/change:

- `backend/app/api/code_reviews.py`
- `backend/app/services/code_review_service.py`
- `backend/app/models/artifacts.py`
- `frontend/features/developer-workspace/`
- Tests

Do not change:

- Do not execute uploaded code.
- Do not produce production-ready generated code.

Acceptance criteria:

- User can request analysis/review for uploaded `.py` or `.sql`.
- Review output is stored and typed.
- UI shows findings, assumptions, limitations, and risks.

Test command:

```bash
cd backend && pytest
cd ../frontend && npm run lint
```

Next task: Task 16.

## Task 16: Add Code Conversion Run Metadata

Goal: Track draft conversion or notebook generation without overpromising automation.

Scope:

- Conversion run metadata.
- Notebook generation run metadata.
- Input artifact version.
- Output artifact version.
- Assumptions and limitations.
- Draft approval status.

Related prompts: `developer/code_migration`, `developer/notebook_generator`. See `docs/agents/PROMPT_ENGINEERING.md`.

Files to create/change:

- `backend/app/api/code_conversion.py`
- `backend/app/services/code_conversion_service.py`
- `backend/app/services/notebook_generation_service.py`
- `backend/app/models/artifacts.py`
- Tests

Do not change:

- Automatic deployment behavior.
- Full notebook runtime.
- Arbitrary code execution.

Acceptance criteria:

- Conversion run can be created.
- Output artifact version remains draft.
- Assumptions and limitations are persisted.
- Human approval is required before production use.

Test command:

```bash
cd backend && pytest
```

Next task: Task 17.

## Task 17: Add Artifact Version History and Approval UI

Goal: Let users review, approve, or reject generated draft artifacts.

Scope:

- Version history drawer.
- Approval modal.
- Approve/reject APIs.
- Decision notes.
- Audit log entry.

Files to create/change:

- `backend/app/api/artifact_approvals.py`
- `backend/app/services/artifact_approval_service.py`
- `frontend/features/developer-workspace/components/VersionHistoryDrawer.tsx`
- `frontend/features/developer-workspace/components/ApprovalModal.tsx`
- `frontend/lib/api/artifacts.ts`
- Tests

Do not change:

- Project approval workflow semantics unless docs are updated.
- Artifact storage internals.

Acceptance criteria:

- User can inspect artifact versions.
- Draft and approved statuses are clear.
- Generated artifact can be approved or rejected.
- Decision note and audit record are stored.

Test command:

```bash
cd backend && pytest
cd ../frontend && npm run lint
```

Next task: Task 18.

## Task 18: Add Basic Validation and Reconciliation

Goal: Add MVP validation/recon foundation without building a full execution engine.

Scope:

- Validation rule metadata.
- Validation runs.
- Row count rule.
- Null and duplicate check definitions.
- Recon run and summary metadata.
- Report metadata.
- Validation/recon UI pages.

Related prompts: `bmad/qa_validation_plan`, `bmad/recon_plan`. See `docs/agents/PROMPT_ENGINEERING.md`.

Files to create/change:

- `validation-engine/`
- `backend/app/models/validation.py`
- `backend/app/models/reconciliation.py`
- `backend/app/schemas/validation.py`
- `backend/app/api/validation.py`
- `backend/app/api/reconciliation.py`
- `backend/app/services/validation_service.py`
- `backend/app/services/reconciliation_service.py`
- `frontend/features/validation/`
- `frontend/features/reconciliation/`
- `frontend/app/projects/[id]/validation/`
- `frontend/app/projects/[id]/recon/`
- Migrations and tests

Do not change:

- Full Great Expectations UI.
- Full dbt orchestration.
- Full production data movement.
- Full customer business data storage.

Acceptance criteria:

- Validation rule metadata can be created.
- Recon summary can be stored.
- Results are project-scoped.
- UI shows basic validation/recon status and failed checks.

Test command:

```bash
cd backend && pytest
cd ../frontend && npm run lint
```

Next task: Task 19.

## Task 19: Add Audit Log Foundation

Goal: Add lightweight audit logs for MVP-sensitive actions.

Scope:

- Audit log model.
- Audit service.
- Audit API.
- Admin audit log UI.
- Audit events for auth, LLM keys, projects, agent approvals, uploads, artifact approvals, validation/recon runs, and exports.

Files to create/change:

- `backend/app/models/audit.py`
- `backend/app/schemas/audit.py`
- `backend/app/services/audit_log_service.py`
- `backend/app/api/audit.py`
- `frontend/app/admin/audit-logs/`
- Tests

Do not change:

- Full governance suite.
- Long-term retention policy beyond documented defaults.

Acceptance criteria:

- Sensitive actions write audit records.
- Admin can view audit logs.
- Secrets are not logged.

Test command:

```bash
cd backend && pytest
cd ../frontend && npm run lint
```

Next task: Task 20.

## Task 20: Add System Health API and UI

Goal: Add basic observability for MVP.

Scope:

- Backend health details.
- Database health.
- Redis health.
- Temporal health.
- Worker heartbeat/status.
- Artifact storage path check.
- Admin system health UI.

Files to create/change:

- `backend/app/models/observability.py`
- `backend/app/schemas/system.py`
- `backend/app/services/observability_service.py`
- `backend/app/api/system.py`
- `frontend/app/admin/system-health/`
- Tests

Do not change:

- Advanced metrics dashboard.
- Full monitoring/alerting stack.

Acceptance criteria:

- `/api/v1/system/health` returns component status.
- Admin UI displays health state.
- Failed components are visible.

Test command:

```bash
cd backend && pytest
cd ../frontend && npm run lint
```

Next task: Task 21.

## Task 21: Docker Compose Stabilization

Goal: Verify the self-hosted Docker Compose flow matches the implemented services.

Scope:

- Compose service names.
- Ports.
- Environment variables.
- Local artifact storage volume/path.
- PostgreSQL persistence.
- Redis and Temporal connectivity.
- Worker startup.

Files to create/change:

- `docker-compose.yml`
- `docker-compose.dev.yml`
- `.env.example`
- `docs/deployment/INSTALLATION.md`
- `docs/project-planning/DOCKER_RELEASE_PLAN.md` if implementation differs from plan

Do not change:

- Helm chart.
- Production deployment automation.

Acceptance criteria:

- Docker Compose config passes.
- Services start together.
- Frontend, backend, and Temporal UI are reachable.
- Artifact storage path is writable.

Test command:

```bash
docker compose config
docker compose up -d
docker compose ps
```

Next task: Task 22.

## Task 22: README Installation Validation

Goal: Ensure public install docs match the actual MVP runtime.

Scope:

- README quick start.
- Installation guide.
- Environment variable documentation.
- Service URLs.
- First admin setup steps.
- LLM setup steps.
- Safe execution note.

Files to create/change:

- `README.md`
- `docs/deployment/INSTALLATION.md`
- `.env.example` if env names changed

Do not change:

- Runtime behavior.
- Product scope.

Acceptance criteria:

- Install commands match actual Docker Compose files.
- URLs and ports are accurate.
- Docs repeat no arbitrary uploaded-code execution in MVP.
- Docs explain PostgreSQL metadata and file-based artifact storage.

Test command:

```bash
rg -n "docker compose|localhost:8080|localhost:8000|localhost:8233|Helix Migration|helix-ai-migration" README.md docs/deployment/INSTALLATION.md
```

Next task: Task 23.

## Task 23: MVP Release Readiness

Goal: Prepare the first open-source MVP release.

Scope:

- Run acceptance criteria review.
- Run release checklist.
- Verify docs and code align.
- Verify no secrets are committed.
- Verify screenshots/demo notes exist where expected.
- Verify Docker image names.

Files to create/change:

- `docs/project-planning/ACCEPTANCE_CRITERIA.md` if criteria changed
- `docs/project-planning/RELEASE_CHECKLIST.md` if release gates changed
- `README.md`
- `SECURITY.md`
- GitHub metadata files if needed

Do not change:

- MVP scope without updating planning docs.
- Application behavior unrelated to release readiness.

Acceptance criteria:

- MVP acceptance criteria pass.
- Release checklist is complete.
- Docker setup works from a clean checkout.
- No doc claims full automatic production migration.
- No doc says uploaded code is executed in MVP.

Test command:

```bash
rg -n "full automatic production|fully automated production|uploaded code is executed|execute uploaded code in MVP|production-ready generated" README.md docs *.md
docker compose config
```

Next task: Public MVP release.
