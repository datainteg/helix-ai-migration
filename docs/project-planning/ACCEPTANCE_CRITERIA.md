# MVP Acceptance Criteria

## Install Criteria

- `docker compose config` passes.
- `docker compose up -d` starts required services.
- Frontend is reachable.
- Backend health endpoint is reachable.
- Temporal UI is reachable.
- PostgreSQL data persists across container restart.

## Admin Criteria

- First admin setup works once.
- Admin can log in.
- Admin can create users and assign roles.
- RBAC prevents unauthorized admin actions.

## LLM Settings Criteria

- Admin can create LLM provider.
- API key is encrypted before storage.
- UI and API show only masked key.
- Key rotation works and writes audit log.
- Agent-wise model mapping can be configured.

## Project Criteria

- User can create project.
- User can create subproject.
- User can add requirement.
- User can view project workspace.
- Project records are organization-scoped.

## Agent Workflow Criteria

- BMAD workflow starts from a requirement.
- Agent outputs validate against typed schemas.
- Agent outputs are stored in PostgreSQL.
- Human approval gate blocks later steps.
- Failures are visible and retryable.

## Developer Workspace Criteria

- User can upload `.py` and `.sql` files.
- Upload stores metadata and content hash.
- Artifact content is stored outside PostgreSQL.
- Uploaded code is not executed.
- Code analysis output is typed and stored.
- Code review summary is visible.
- Draft generated output is marked as draft.
- Side-by-side diff is visible.
- Human approval or rejection is stored and audited.

## Validation/Reconciliation Criteria

- User can create basic validation rule metadata.
- Basic row count, null, and duplicate check definitions can be represented.
- Reconciliation summary can be generated from metadata.
- Report metadata can be stored and viewed.

## Security Criteria

- API keys and SMTP secrets are encrypted or externally referenced.
- Secrets are masked in UI and API.
- RBAC is enforced by backend.
- Organization data is separated.
- Production business data is not stored by default.
- Uploaded code is treated as untrusted input.

## Audit Criteria

- Login events are audited.
- Admin changes are audited.
- LLM provider changes and key rotation are audited.
- Agent workflow approvals are audited.
- Artifact upload and artifact approvals are audited.
- Report exports are audited.

## UI Criteria

- Navigation is clear for admin, project, agent, validation, recon, and developer workspace areas.
- Loading, empty, error, and permission states exist.
- Approval actions are explicit.
- Generated artifacts show assumptions, limitations, and draft status.
- UI is usable on desktop and basic tablet review flows.
