# API Design

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

Helix Migration backend APIs should be predictable, typed, documented through OpenAPI, and safe for enterprise self-hosted deployments.

## API Conventions

- Base path: `/api/v1`
- Use JSON request and response bodies.
- Use plural resource names.
- Use snake_case for JSON fields unless frontend contract later standardizes otherwise.
- Use typed Pydantic models for all inputs and outputs.
- Use consistent pagination, filtering, and error responses.
- Never return full secrets.

## Route Naming

```text
/api/v1/auth/...
/api/v1/admin/...
/api/v1/organizations/...
/api/v1/projects/...
/api/v1/subprojects/...
/api/v1/sources/...
/api/v1/targets/...
/api/v1/schemas/...
/api/v1/agents/...
/api/v1/llm-providers/...
/api/v1/validation/...
/api/v1/reconciliation/...
/api/v1/reports/...
/api/v1/audit-logs/...
/api/v1/system/...
```

## Auth APIs

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/auth/login` | Login |
| `POST` | `/auth/logout` | Logout |
| `POST` | `/auth/refresh` | Refresh token |
| `GET` | `/auth/me` | Current user |
| `POST` | `/auth/first-admin` | Create first admin during setup |

## Admin APIs

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/admin/users` | List users |
| `POST` | `/admin/users` | Create user |
| `PATCH` | `/admin/users/{user_id}` | Update user |
| `DELETE` | `/admin/users/{user_id}` | Deactivate or delete user according to retention policy |
| `GET` | `/admin/roles` | List roles |
| `POST` | `/admin/roles` | Create role |
| `DELETE` | `/admin/roles/{role_id}` | Delete custom role when unused |
| `GET` | `/admin/system-health` | System health |

## Project APIs

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/projects` | List projects |
| `POST` | `/projects` | Create project |
| `GET` | `/projects/{project_id}` | Get project |
| `PATCH` | `/projects/{project_id}` | Update project |
| `DELETE` | `/projects/{project_id}` | Archive or delete project according to retention policy |
| `POST` | `/projects/{project_id}/requirements` | Add requirement |
| `GET` | `/projects/{project_id}/activity` | Project activity |

## Source and Target APIs

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/projects/{project_id}/sources` | List source systems |
| `POST` | `/projects/{project_id}/sources` | Add source system |
| `DELETE` | `/sources/{source_id}` | Remove source metadata and related connection reference |
| `POST` | `/sources/{source_id}/test-connection` | Test source connection |
| `POST` | `/sources/{source_id}/scan-schema` | Start source schema scan |
| `GET` | `/projects/{project_id}/targets` | List target systems |
| `POST` | `/projects/{project_id}/targets` | Add target system |
| `DELETE` | `/targets/{target_id}` | Remove target metadata and related connection reference |
| `POST` | `/targets/{target_id}/test-connection` | Test target connection |

## Schema APIs

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/projects/{project_id}/schemas` | List schemas |
| `GET` | `/schemas/{schema_id}/tables` | List tables |
| `GET` | `/tables/{table_id}/columns` | List columns |
| `POST` | `/projects/{project_id}/schema-snapshots` | Create schema snapshot |
| `POST` | `/projects/{project_id}/schema-compare` | Compare source and target schema |

## Agent APIs

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/projects/{project_id}/agent-workflows` | Start planning workflow |
| `GET` | `/projects/{project_id}/agent-workflows` | List workflows |
| `GET` | `/agent-workflows/{workflow_id}` | Get workflow state |
| `GET` | `/agent-tasks/{task_id}` | Get task |
| `GET` | `/agent-tasks/{task_id}/outputs` | Get typed outputs |
| `POST` | `/agent-workflows/{workflow_id}/approve` | Approve workflow step |
| `POST` | `/agent-workflows/{workflow_id}/request-changes` | Request changes |

## LLM Provider APIs

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/llm-providers` | List providers |
| `POST` | `/llm-providers` | Create provider |
| `PATCH` | `/llm-providers/{provider_id}` | Update provider |
| `DELETE` | `/llm-providers/{provider_id}` | Disable or delete provider configuration |
| `POST` | `/llm-providers/{provider_id}/rotate-key` | Rotate API key |
| `POST` | `/llm-providers/{provider_id}/test` | Test provider |
| `GET` | `/llm-agent-mappings` | List agent mappings |
| `PUT` | `/llm-agent-mappings` | Update agent mappings |

## Validation APIs

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/projects/{project_id}/validation-rules` | List rules |
| `POST` | `/projects/{project_id}/validation-rules` | Create rule |
| `DELETE` | `/validation-rules/{rule_id}` | Delete validation rule |
| `POST` | `/projects/{project_id}/validation-runs` | Start run |
| `GET` | `/validation-runs/{run_id}` | Get run |
| `GET` | `/validation-runs/{run_id}/results` | Get results |

## Reconciliation APIs

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/projects/{project_id}/recon-runs` | Start recon run |
| `GET` | `/recon-runs/{run_id}` | Get recon run |
| `GET` | `/recon-runs/{run_id}/results` | Get results |
| `GET` | `/recon-runs/{run_id}/mismatches` | Get mismatch summaries |

## Report APIs

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/projects/{project_id}/reports` | List reports |
| `POST` | `/projects/{project_id}/reports` | Generate report |
| `GET` | `/reports/{report_id}` | Get report metadata |
| `POST` | `/reports/{report_id}/exports` | Export report |

## Audit APIs

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/audit-logs` | List audit logs |
| `GET` | `/projects/{project_id}/audit-logs` | Project audit logs |

## Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "provider_type",
        "message": "Unsupported provider"
      }
    ],
    "request_id": "req_123"
  }
}
```

## Pagination

Use cursor or page-based pagination consistently:

```json
{
  "items": [],
  "page": 1,
  "page_size": 50,
  "total": 200
}
```

## Versioning

- Start with `/api/v1`.
- Avoid breaking changes within a version.
- Document deprecations.
- Keep OpenAPI current.

## OpenAPI Docs

FastAPI should expose:

- `/docs` for Swagger UI
- `/redoc` for ReDoc
- `/openapi.json` for generated clients

## Developer Execution APIs

Developer execution APIs manage uploaded artifacts, reviews, conversion runs, notebook generation, DAG review, generated artifact approvals, and version history. Generated code and notebooks are drafts until approved by humans.

### Artifact APIs

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/projects/{project_id}/artifacts/upload` | Upload code artifact and create metadata |
| `GET` | `/api/v1/projects/{project_id}/artifacts` | List project artifacts |
| `GET` | `/api/v1/artifacts/{artifact_id}` | Get artifact metadata |
| `DELETE` | `/api/v1/artifacts/{artifact_id}` | Archive artifact metadata and versions according to retention policy |
| `GET` | `/api/v1/artifacts/{artifact_id}/versions` | List artifact versions |
| `GET` | `/api/v1/artifacts/{artifact_id}/diff` | Get latest source vs generated diff metadata |

### Code Review APIs

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/artifacts/{artifact_id}/analyze` | Run Code Analyzer Agent |
| `POST` | `/api/v1/artifacts/{artifact_id}/review` | Run Code Review Agent |
| `GET` | `/api/v1/code-reviews/{review_id}` | Get review summary and comments |

### Code Conversion APIs

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/artifacts/{artifact_id}/convert` | Start draft code conversion |
| `POST` | `/api/v1/artifacts/{artifact_id}/generate-notebook` | Generate Databricks notebook draft |
| `POST` | `/api/v1/artifacts/{artifact_id}/notebook` | Alias for notebook draft generation |
| `GET` | `/api/v1/conversion-runs/{run_id}` | Get conversion run status and output metadata |

### DAG Review APIs

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/artifacts/{artifact_id}/dag-review` | Run DAG / Workflow Review Agent |
| `GET` | `/api/v1/dag-review-runs/{run_id}` | Get DAG review results |

### Approval APIs

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/artifact-versions/{version_id}/approve` | Approve generated artifact version |
| `POST` | `/api/v1/artifact-versions/{version_id}/reject` | Reject generated artifact version |

Additional artifact version route:

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/artifacts/{artifact_id}/versions` | Create artifact version metadata |
| `GET` | `/api/v1/artifact-versions/{version_id}` | Get one artifact version |

## Governance APIs

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/v1/audit-logs` | List audit logs |
| `GET` | `/api/v1/agent-decision-logs` | List agent decision logs |
| `GET` | `/api/v1/approval-history` | List approval history |
| `GET` | `/api/v1/llm-usage-logs` | List LLM usage logs |

## Observability APIs

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/v1/system/health` | System health |
| `GET` | `/api/v1/system/workers` | Worker status |
| `GET` | `/api/v1/system/workflows` | Workflow status |
| `GET` | `/api/v1/system/failed-jobs` | Failed jobs |
| `GET` | `/api/v1/system/llm-metrics` | LLM usage and latency metrics |

## Template APIs

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/v1/templates` | List templates |
| `POST` | `/api/v1/templates` | Create template metadata |
| `GET` | `/api/v1/templates/{template_id}` | Get template |
| `POST` | `/api/v1/templates/{template_id}/apply` | Apply template |
| `DELETE` | `/api/v1/templates/{template_id}` | Delete custom template metadata |

## Plugin APIs

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/v1/plugins` | List plugins |
| `POST` | `/api/v1/plugins/install` | Install plugin |
| `POST` | `/api/v1/plugins/{plugin_id}/enable` | Enable plugin |
| `POST` | `/api/v1/plugins/{plugin_id}/disable` | Disable plugin |

## Notification APIs

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/v1/notification-channels` | List notification channels |
| `POST` | `/api/v1/notification-channels` | Create notification channel |
| `GET` | `/api/v1/notification-rules` | List notification rules |
| `POST` | `/api/v1/notification-rules` | Create notification rule |
| `GET` | `/api/v1/admin/notifications/smtp` | Get masked SMTP notification configuration |
| `PUT` | `/api/v1/admin/notifications/smtp` | Create or update SMTP notification configuration |
| `POST` | `/api/v1/admin/notifications/smtp/test` | Send SMTP test email |

## Import / Export APIs

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/projects/{project_id}/export` | Export project package |
| `POST` | `/api/v1/projects/import` | Import project configuration |
| `GET` | `/api/v1/export-jobs/{job_id}` | Get export job status |
