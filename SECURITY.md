# Security

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

Helix Migration is designed for enterprise, self-hosted migration workflows. Security must be built into storage, APIs, agent workflows, admin actions, and Docker deployment.

## Secrets Handling

Secrets include:

- LLM provider API keys
- Custom model API keys
- Database passwords
- Connector credentials
- JWT secrets
- Encryption keys

Rules:

- Never commit secrets to Git.
- Never store API keys in plaintext.
- Never display full API keys after save.
- Never log decrypted secrets.
- Mask keys in UI and API responses.
- Support key rotation.

## API Key Encryption

- Store API keys in encrypted fields.
- Keep encrypted secrets in dedicated tables.
- Track key version and rotation timestamp.
- Use environment-managed encryption keys.
- Rotate keys through auditable backend APIs.

Masked key example:

```text
sk-********************9f3a
```

## RBAC

Role-based access control should apply to:

- Admin panel
- User management
- LLM provider settings
- Connector settings
- Project access
- Agent workflow approval
- Validation and recon execution
- Report export
- Audit log access

Suggested roles:

- Super Admin
- Admin
- Project Manager
- Architect
- Data Engineer
- QA Engineer
- Viewer

## Authentication

The backend should support secure login, token refresh, logout, and first-admin setup. Future enterprise features may include SSO, LDAP, and Active Directory integration.

## Authorization

Authorization must be enforced in backend services, not only in the frontend. Every tenant-owned resource should be checked against organization membership and role permissions.

## Safe Metadata Storage

Helix Migration stores metadata by default:

- Schemas
- Tables
- Columns
- Row counts
- Validation summaries
- Reconciliation summaries
- Reports and audit records

Do not store full production business data unless explicitly configured.

## Tenant Separation

- Every tenant-owned table should include `organization_id` directly or through a strict project relationship.
- API queries must scope by organization.
- Admin operations must be audited.
- Cross-organization access is a security defect.

## Audit Logs

Audit events should include:

- Login and logout
- Failed login
- User changes
- Role changes
- LLM provider changes
- API key rotation
- Connector credential changes
- Agent workflow approval
- Validation and recon execution
- Report export
- System setting changes
- Artifact upload, review, conversion, generated artifact approval, and export

## Docker Security

- Use secure environment values in production.
- Do not expose PostgreSQL or Redis publicly.
- Use private Docker networks.
- Run behind TLS.
- Keep images updated.
- Use least-privilege containers where possible.
- Back up PostgreSQL securely.

## Vulnerability Reporting

Until a formal process is published, security issues should be reported privately to the maintainers through the project website or repository contact channel. Do not disclose exploitable security issues publicly before maintainers have had time to respond.

## Security Review Checklist

- Are secrets encrypted?
- Are keys masked?
- Is RBAC enforced in backend code?
- Are organization filters applied?
- Are audit logs written?
- Are external calls timeout-limited?
- Are LLM prompts protected from leaking secrets?
- Are Docker defaults safe for local use and documented for production?

## Developer Execution Security

- Do not execute uploaded code during analysis or review.
- Treat uploaded artifacts as untrusted input.
- Restrict upload types in MVP to `.py` and `.sql`.
- Scan uploaded content for hardcoded secrets and risky patterns.
- Store artifact metadata, hashes, lineage, and approvals in PostgreSQL.
- Store actual file content through a storage abstraction and prepare for object storage.
- Keep generated code as draft until human approval.
- Audit upload, analysis, conversion, approval, rejection, and export actions.
- Encrypt SMTP passwords and webhook secrets before storage, or reference them through external secret managers.
- Mask SMTP passwords and webhook secrets in all UI/API responses.

## Rate Limiting

Redis-backed rate limiting should protect the platform from abuse:

- Per-endpoint rate limits for auth endpoints (e.g., 5 login attempts per minute per IP).
- Per-user rate limits for LLM-triggering endpoints (agent workflows, code analysis, code review).
- Global rate limits for unauthenticated endpoints.
- Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`.
- Rate limit exceeded responses should return HTTP 429 with a descriptive error body.
- Admin APIs and health endpoints should have higher or no limits.

## Data Retention

Configurable retention policies should cover:

| Data category | Default retention | Configurable? |
|---|---|---|
| Audit logs | 365 days | Yes, per organization |
| Artifact versions | All versions kept unless manually purged | Yes |
| LLM usage logs | 90 days | Yes |
| Agent decision logs | Linked to project lifecycle | Per project |
| Uploaded files (MVP) | Retained until project deletion | Per project |
| Failed job records | 30 days | Yes |
| System health checks | 7 days | No |

Retention cleanup should run as a scheduled Temporal workflow. Deleted records should be soft-deleted first (30-day grace period) before permanent removal.

## Enterprise Security Additions

Uploaded code is treated as untrusted input. MVP supports safe code analysis only and must not execute arbitrary uploaded code.

Security rules:

- API keys must be encrypted before storing.
- Never display full API keys after save.
- Show only masked keys.
- Support key rotation.
- Add audit logs.
- Use RBAC.
- Keep organization-level separation.
- Do not store production business data unless explicitly configured.
- Do not execute uploaded code directly in MVP.
- Store uploaded/generated files outside PostgreSQL through artifact storage.
- Scan uploaded artifacts for hardcoded secrets and risky patterns.
- Keep generated code as draft until human approval.

## Related Docs

| Doc | What it covers |
|---|---|
| `docs/security/SECRETS_MANAGEMENT.md` | Encryption strategy, key rotation, external secret managers |
| `docs/security/SAFE_EXECUTION.md` | MVP no-execution rule, future sandboxing |
| `docs/governance/GOVERNANCE_AUDIT.md` | Audit log design, approval history, exportable reports |
| `docs/storage/ARTIFACT_STORAGE.md` | Artifact metadata separation from file storage |
| `docs/notifications/NOTIFICATION_SYSTEM.md` | SMTP security, encrypted notification secrets |
| `DATABASE_DESIGN.md` | Encrypted secrets storage, audit log schema |

Secrets management roadmap:

- Encrypted database storage for MVP
- Docker secrets
- HashiCorp Vault
- AWS Secrets Manager
- Azure Key Vault
- GCP Secret Manager

Data retention should be configurable for audit logs, artifact versions, generated reports, LLM usage logs, and uploaded files. Plugin security requires least privilege, explicit enablement, tenant boundaries, and audit logs for install/enable/disable actions.
