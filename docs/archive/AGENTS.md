# AGENTS.md

## Project Identity

| Item | Value |
|---|---|
| Product | Helix Migration |
| Repository | helix-ai-migration |
| Tagline | Open-source AI-powered migration and validation platform. |
| Frontend image | datainteg/helix-ai-migration-frontend |
| Backend image | datainteg/helix-ai-migration-backend |
| Worker image | datainteg/helix-ai-migration-worker |

## Codex Instructions for Helix Migration

Helix Migration is an open-source, self-hosted AI-powered migration and validation platform. It helps enterprises plan, validate, reconcile, and manage complex data migrations through intelligent multi-agent workflows.

Product identity must stay consistent:

| Item | Value |
|---|---|
| Product | Helix Migration |
| Repository | helix-ai-migration |
| Website | helix.datainteg.io |
| GitHub | github.com/datainteg/helix-ai-migration |
| Tagline | Open-source AI-powered migration and validation platform. |
| Frontend image | datainteg/helix-ai-migration-frontend |
| Backend image | datainteg/helix-ai-migration-backend |
| Worker image | datainteg/helix-ai-migration-worker |

## Operating Rules

- Read `README.md` before making product, architecture, or implementation decisions.
- Treat the current repository status as planning and architecture phase until implementation is explicitly requested.
- Do not implement application code when the task asks for planning or documentation only.
- Keep Helix Migration positioned as an enterprise migration command center, not a chatbot.
- Keep the MVP focused on installable foundation, admin setup, LLM configuration, project setup, metadata storage, agent planning, validation, and reconciliation reports.
- Prefer small, reviewable changes over broad rewrites.
- Avoid unrelated features, speculative integrations, and hidden behavior.
- Update documentation when architecture, APIs, security posture, Docker behavior, or workflow contracts change.

## Do Not Rules

- Do not store production customer business data by default.
- Do not display full API keys after save.
- Do not store API keys or provider secrets in plaintext.
- Do not generate random unstructured agent output.
- Do not let agent responses bypass typed schemas.
- Do not skip human approval for critical migration planning outputs.
- Do not hard-code one LLM provider as the only supported provider.
- Do not tightly couple the platform identity to BMAD only; BMAD is the methodology, not the whole product.
- Do not add application source code unless the user explicitly asks for implementation.
- Do not present generated migration code or notebook content as production-ready.

## Expected Repository Structure

Future implementation should follow the README direction:

```text
helix-ai-migration/
  frontend/
  backend/
  worker/
  agents/
  connectors/
  validation-engine/
  docs/
  deployment/
  examples/
  docker-compose.yml
  docker-compose.dev.yml
  .env.example
```

If files do not exist yet, create them only when an implementation task requires them.

## Frontend Rules

- Use Next.js, TypeScript, Tailwind CSS, shadcn/ui, React Flow, and Framer Motion.
- Build a real enterprise application experience, not a marketing shell.
- Support business mode and engineering mode.
- Use React Flow for agent workflows, lineage, validation flow, and dependency views.
- Use typed API clients and shared response contracts when available.
- Keep admin, dashboard, project workspace, connector hub, validation center, recon reports, and settings as clear product areas.
- Avoid decorative UI that reduces scannability for enterprise users.
- Ensure RBAC affects visible actions and navigation.

## Backend Rules

- Use FastAPI and Python.
- Use Pydantic for request and response validation.
- Use SQLAlchemy or SQLModel for persistence.
- Use Alembic for database migrations.
- Keep routers thin; put business logic in services.
- Use consistent API response and error shapes.
- Add audit logs for security-sensitive actions.
- Never return raw secret values from API responses.

## Agent Runtime Rules

- Use BMAD as the default migration methodology.
- Use LangGraph for multi-agent orchestration.
- Use PydanticAI for structured model outputs.
- Use Temporal OSS for durable workflow execution, retries, and long-running workflows.
- Use an LLM router for provider and model routing.
- Store agent tasks, outputs, prompt versions, approvals, failures, and workflow state in PostgreSQL.
- Every agent output must validate against a typed schema before storage.
- Store confidence, assumptions, risks, unresolved questions, and provenance where useful.

Required agent flow:

```text
User Requirement
  -> Business Analyst Agent
  -> Architect Agent
  -> Human Approval
  -> Data Engineer Agent
  -> QA / Validation Agent
  -> Recon Agent
  -> DevOps Agent
  -> PM Agent
  -> Final Review & Sign-off
```

## Database Rules

- PostgreSQL is the global metadata store.
- Store metadata, not full customer business data by default.
- Use organization-level separation on all tenant-owned records.
- Use consistent IDs, timestamps, created_by, updated_by, and audit metadata.
- Encrypt secrets before storing.
- Use migrations for all schema changes.

Metadata examples:

- Users, organizations, roles, and permissions
- Projects and subprojects
- Source and target systems
- Schemas, tables, columns, and schema snapshots
- Agent tasks, outputs, memory, and prompt versions
- Validation rules, validation results, recon results, reports, approvals, and audit logs
- LLM provider settings and agent model mappings
- Code artifacts, artifact versions, review summaries, conversion runs, artifact approvals, lineage, and dependencies

## Security Rules

- Encrypt API keys and connection secrets before storage.
- Mask saved keys in the UI and API.
- Support key rotation.
- Add audit logs for login, provider changes, connection changes, approvals, exports, and admin actions.
- Enforce RBAC at the API layer.
- Keep organization data separated.
- Do not log secrets, raw tokens, or full connection strings.
- Use secure defaults for Docker deployments.

## Docker Rules

- Use separate images for frontend, backend, and worker:
  - `datainteg/helix-ai-migration-frontend`
  - `datainteg/helix-ai-migration-backend`
  - `datainteg/helix-ai-migration-worker`
- Docker Compose should include PostgreSQL, Redis, Temporal, and Temporal UI.
- Keep local setup simple and self-hosted.
- Future Helm support should build on the same service boundaries.

## Testing Rules

- Add tests with each implementation task.
- Backend changes should include unit tests and API tests.
- Agent changes should include schema validation and failure-path tests.
- Frontend changes should include component and interaction coverage where practical.
- Docker changes should include a startup verification path.
- Security-sensitive changes require negative tests.

## Task-by-Task Codex Workflow

1. Read the relevant documentation and current files.
2. Identify the smallest safe change.
3. State assumptions if implementation depends on missing choices.
4. Edit only required files.
5. Keep contracts typed and explicit.
6. Run focused checks.
7. Report changed files, verification, and next step.

## MVP Focus

MVP should prioritize:

- Docker Compose installation
- First admin setup
- User, role, and organization foundation
- LLM provider configuration
- Agent-wise model mapping
- Project and subproject setup
- Source/target metadata capture
- BMAD planning workflow with typed outputs
- Human approval
- Basic validation and reconciliation reports
- Audit logs
- Developer Workspace MVP for `.py` and `.sql` upload, code analysis, review summary, draft conversion/notebook structure, side-by-side diff, artifact versioning, and human approval

## Developer Execution Rules

- Helix Migration generates draft migration code, notebook structures, validation plans, and reconciliation reports that must be reviewed and approved by humans before production use.
- Uploaded code must not be executed during analysis.
- Code Analyzer, Code Review, Code Migration, Notebook Generator, DAG / Workflow Review, and Version Control agents must return typed schemas.
- Store artifact metadata, content hashes, versions, approvals, lineage, and dependencies in PostgreSQL.
- Use local filesystem artifact storage for MVP and MinIO/S3-compatible storage later; PostgreSQL remains the metadata source of truth.
- Always expose assumptions, limitations, risks, and approval status for generated artifacts.
