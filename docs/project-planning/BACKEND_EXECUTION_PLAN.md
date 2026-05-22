# Backend Execution Plan

## Stack

- FastAPI
- Python
- PostgreSQL
- Redis
- SQLAlchemy or SQLModel
- Alembic
- Pydantic

## FastAPI Structure

```text
backend/app/
  api/
  auth/
  core/
  db/
  models/
  schemas/
  services/
  storage/
  main.py
```

## Config

Configuration should cover:

- App environment
- Database URL
- Redis URL
- Temporal address
- JWT secret
- Encryption key
- Local artifact storage path
- LLM provider defaults
- SMTP settings metadata when enabled

## Auth

- First admin setup
- Login/logout/refresh
- Current user
- Password hashing
- JWT handling
- RBAC dependencies
- Organization scoping

## Database

- SQLAlchemy or SQLModel models
- Alembic migrations
- PostgreSQL as metadata store
- No full production business data by default
- Artifact content outside PostgreSQL

## Routers

| Router | Purpose |
|---|---|
| `auth` | Login and first admin |
| `admin` | Users, roles, system settings |
| `llm_providers` | Provider configuration and key rotation |
| `projects` | Projects, subprojects, requirements |
| `metadata` | Source/target schema metadata |
| `agents` | Agent workflows, tasks, outputs, approvals |
| `artifacts` | Upload metadata, versions, reviews, approvals |
| `validation` | Rules and validation runs |
| `reconciliation` | Recon runs and results |
| `reports` | Report metadata and exports |
| `audit` | Audit logs |
| `system` | Health and observability |

## Services

- `AuthService`
- `UserService`
- `ProjectService`
- `LLMProviderService`
- `LLMRouterService`
- `AgentWorkflowService`
- `ArtifactService`
- `ArtifactVersionService`
- `CodeReviewService`
- `CodeConversionService`
- `NotebookGenerationService`
- `DAGReviewService`
- `ApprovalService`
- `AuditLogService`
- `ObservabilityService`
- `ValidationService`
- `ReconciliationService`
- `ReportService`
- `HealthService`
- `SecretService`

## Schemas

All APIs should use Pydantic request/response schemas. Agent outputs must use typed schemas and should include assumptions, limitations, risks, confidence where useful, model/provider metadata, and prompt version references.

## LLM Provider Service

- Encrypt API keys before storage.
- Return masked values only.
- Support key rotation.
- Test provider connectivity.
- Support OpenAI / ChatGPT, Google Gemini, Anthropic Claude, DeepSeek, OpenRouter, custom OpenAI-compatible APIs, and local model URL.

## Artifact Service

- Accept `.py` and `.sql` uploads in MVP.
- Treat uploaded code as untrusted input.
- Store metadata and content hashes in PostgreSQL.
- Store files in local artifact storage for MVP.
- Do not execute uploaded code.

## Audit and Health

- Write audit logs for login, admin, LLM, project, workflow, artifact, approval, and export actions.
- Provide health checks for backend, database, Redis, Temporal, worker, and artifact storage.

## Testing

- Unit tests for services.
- API tests for routers.
- Migration tests for core tables.
- Secret masking tests.
- RBAC and organization isolation tests.
- Agent schema validation tests.
- Artifact upload safety tests.

## Related Architecture Docs

| Doc | What it covers |
|---|---|
| `ARCHITECTURE.md` | Overall platform architecture, layer responsibilities |
| `API_DESIGN.md` | Full API contract, routes, error format, pagination |
| `DATABASE_DESIGN.md` | Table groups, relationships, indexes, encryption strategy |
| `docs/backend/BACKEND_GUIDE.md` | Router list, services, models, auth/authorization, error handling |
| `docs/deployment/INSTALLATION.md` | Docker Compose setup, env vars, artifact storage config |
| `TESTING.md` | Test pyramid, agent testing, security tests, mock LLM provider |
