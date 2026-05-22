# Sprint Plan

## Sprint 1: Foundation

Goal: Create the runnable platform skeleton.

| Track | Tasks |
|---|---|
| Backend | FastAPI shell, config loader, health route |
| Frontend | Next.js shell, app layout, dashboard placeholder |
| Agent | Worker shell and Temporal connectivity placeholder |
| Database | PostgreSQL connection settings |
| Testing | Backend health test, frontend lint baseline, Docker config validation |

Acceptance criteria: Docker Compose topology validates, frontend loads, backend health responds, Temporal UI is planned in compose.

## Sprint 2: Database, Auth, and Admin

Goal: Establish secure identity and admin foundation.

| Track | Tasks |
|---|---|
| Backend | Auth routes, first admin setup, RBAC dependencies |
| Frontend | Login, first admin setup, admin shell |
| Agent | None beyond auth-aware API assumptions |
| Database | Users, organizations, roles, permissions, memberships |
| Testing | Auth API tests, protected route tests, migration tests |

Acceptance criteria: First admin can be created once, login works, protected APIs reject unauthenticated requests.

## Sprint 3: LLM Provider Settings

Goal: Enable safe bring-your-own-key configuration.

| Track | Tasks |
|---|---|
| Backend | LLM provider service, encrypted key storage, masking, rotation, test endpoint |
| Frontend | Admin LLM settings, agent model mapping |
| Agent | LLM router interface contract |
| Database | `llm_providers`, `llm_provider_secrets`, `llm_agent_mappings`, audit records |
| Testing | Secret masking, rotation, provider validation |

Acceptance criteria: Full API keys are never returned, mappings save, provider changes are audited.

## Sprint 4: Project Workspace

Goal: Create migration project and requirement workflows.

| Track | Tasks |
|---|---|
| Backend | Project, subproject, requirement, source/target metadata APIs |
| Frontend | Project list, create project, project detail, requirement intake |
| Agent | Define workflow input contract from requirements |
| Database | Projects, subprojects, requirements, source/target metadata |
| Testing | Project CRUD and organization scoping tests |

Acceptance criteria: User can create a project, add requirement, and view project workspace.

## Sprint 5: BMAD Agent Workflow

Goal: Run the first typed planning workflow.

| Track | Tasks |
|---|---|
| Backend | Agent task APIs, output storage, approval endpoints |
| Frontend | React Flow workflow canvas, agent output viewer, approval UI |
| Agent | BA and Architect agents, typed outputs, approval gate |
| Database | Agent definitions, tasks, outputs, prompts, workflow runs |
| Testing | Schema validation, approval gate, retry/failure visibility |

Acceptance criteria: Workflow starts from a requirement, outputs validate, and later steps wait for human approval.

## Sprint 6: Developer Workspace

Goal: Add safe developer execution foundation.

| Track | Tasks |
|---|---|
| Backend | Artifact metadata, upload API, code review service, conversion run metadata |
| Frontend | Developer workspace, artifact explorer, diff viewer, AI review panel, approval modal |
| Agent | Code Analyzer Agent and Code Review Agent schemas |
| Database | Artifacts, versions, reviews, conversions, approvals, lineage, dependencies |
| Testing | Upload type validation, content hash, no execution, artifact approval |

Acceptance criteria: User uploads `.py` or `.sql`, reviews analysis, sees draft diff, and approves or rejects a version.

## Sprint 7: Validation, Reconciliation, Audit, Health

Goal: Complete the MVP command-center loop.

| Track | Tasks |
|---|---|
| Backend | Validation rules/runs, recon summaries, audit log service, health APIs |
| Frontend | Validation/recon pages, audit logs, system health |
| Agent | QA/Validation and Recon draft outputs |
| Database | Validation, recon, reports, audit, health tables |
| Testing | Validation/recon metadata tests, audit event tests, health tests |

Acceptance criteria: Basic validation/recon report exists, audit logs show key actions, system health page shows service status.

## Sprint 8: Release Hardening

Goal: Prepare public MVP release.

| Track | Tasks |
|---|---|
| Backend | API docs review, error handling, rate-limit plan |
| Frontend | UX polish, empty/loading/error states, screenshots |
| Agent | Prompt and schema documentation pass |
| Database | Migration reset/install validation |
| Testing | Docker Compose smoke test, release checklist |

Acceptance criteria: Docs match implementation, Docker install works from clean checkout, release checklist is complete.
