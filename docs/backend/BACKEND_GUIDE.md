# Backend Guide

Helix Migration backend should be a FastAPI service with clear routers, typed schemas, service-layer business logic, PostgreSQL persistence, and audit-ready security.

## Stack

- FastAPI
- Python
- PostgreSQL
- Redis
- SQLAlchemy or SQLModel
- Alembic
- Pydantic
- Temporal client integration

## Recommended Structure

```text
backend/
  app/
    api/
    auth/
    core/
    db/
    models/
    schemas/
    services/
    integrations/
    main.py
  alembic/
  tests/
  requirements.txt
```

## Routers

Routers should be thin and call services.

Suggested routers:

- `auth`
- `admin_users`
- `organizations`
- `projects`
- `metadata`
- `llm_providers`
- `agents`
- `validation`
- `reconciliation`
- `reports`
- `audit_logs`
- `system`

## Services

Services should own business rules:

- Auth service
- RBAC service
- Organization service
- Project service
- Metadata service
- Secret service
- LLM provider service
- Agent workflow service
- Validation service
- Reconciliation service
- Report service
- Audit service
- Artifact service
- Code review service
- Conversion service
- Artifact version service
- Approval service

## Models

Models should represent database tables and relationships. Tenant-owned models should be organization-scoped directly or through project ownership.

Model groups:

- Identity
- Projects
- Metadata
- LLM providers
- Agents
- Workflows
- Validation
- Reconciliation
- Reports
- Audit
- Artifacts
- Code reviews
- Code conversion runs
- Artifact approvals

## Schemas

Use Pydantic schemas for:

- Request bodies
- Response bodies
- Internal typed payloads
- Agent outputs
- Validation result shapes

Do not return ORM models directly from routes.

## Database Session

- Centralize session creation.
- Use dependency injection for request-scoped sessions.
- Use explicit transactions in services.
- Keep background jobs and Temporal activities session-safe.

## Authentication

Backend should support:

- First admin setup
- Login
- Refresh
- Logout
- Current user
- Password hashing
- Token validation

## Authorization

- Enforce RBAC in backend dependencies or services.
- Check organization membership.
- Check project access.
- Audit denied sensitive operations where useful.

## Config

Use typed configuration for:

- App environment
- Database URL
- Redis URL
- Temporal address
- JWT settings
- Encryption key
- LLM defaults

## Testing

Test:

- Auth flows
- RBAC denial paths
- Organization isolation
- Secret encryption and masking
- LLM provider APIs
- Project APIs
- Agent task lifecycle
- Validation and recon APIs
- Alembic migrations

## Alembic

Rules:

- Every schema change needs a migration.
- Migrations must be reviewable.
- Indexes and constraints belong in migrations.
- Do not rewrite merged migration history.

## Error Handling

Use consistent error responses:

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "You do not have access to this project",
    "details": [],
    "request_id": "req_123"
  }
}
```

## Background Jobs

Use Temporal for durable workflows:

- Agent workflows
- Connector scans
- Validation runs
- Recon runs
- Report generation

Use Redis for cache and short-lived state, not durable workflow truth.

## Developer Execution Backend

Developer Execution services:

- Artifact service
- Code review service
- Conversion service
- Artifact version service
- Approval service

Safe file handling rules:

- Accept only configured file types in MVP, starting with `.py` and `.sql`.
- Do not execute uploaded code.
- Calculate content hashes for uploaded and generated artifacts.
- Store metadata, hashes, lineage, review summaries, and approval state in PostgreSQL.
- Use storage abstraction for file content so local storage can later move to object storage.
- Keep artifact access organization-scoped and project-scoped.
- Treat generated code and notebooks as drafts until approved.

Storage abstraction should separate:

- Artifact metadata in PostgreSQL
- File content in local or object storage
- Content hashes and version records in PostgreSQL
- Review comments and conversion metadata in PostgreSQL

## Enterprise Backend Services

- `ArtifactService`
- `ArtifactVersionService`
- `CodeReviewService`
- `CodeConversionService`
- `NotebookGenerationService`
- `DAGReviewService`
- `ApprovalService`
- `AuditLogService`
- `ObservabilityService`
- `TemplateService`
- `PluginService`
- `NotificationService`
- `ImportExportService`
- `SecretService`
- `SmtpSettingsService`

Do not store uploaded files directly in PostgreSQL. Use a storage abstraction: local filesystem for MVP, MinIO/S3-compatible storage later. PostgreSQL stores metadata, content hashes, storage paths, versions, owner, approval status, provider, and audit trail.

SMTP notification settings should be handled through `NotificationService` and `SmtpSettingsService`. SMTP passwords must be encrypted through `SecretService` or stored as external secret references, masked in responses, and audited on create, update, rotation, and test send.

## Background Jobs

Use Temporal for durable workflows:

- BMAD planning workflows
- Developer code analysis and review runs
- Draft conversion and notebook generation runs
- Connector metadata scans
- Validation and reconciliation runs
- Report exports

Use Redis for cache, rate limiting, and short-lived coordination only. PostgreSQL remains source of truth for workflow metadata, audit logs, and artifact metadata.
