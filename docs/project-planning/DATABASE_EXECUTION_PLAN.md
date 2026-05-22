# Database Execution Plan

## Database Principle

PostgreSQL is the global metadata store. It stores platform metadata, workflow state, summaries, hashes, approvals, audit records, and configuration. It does not store full production business data by default.

Artifact files are stored outside PostgreSQL:

- Local filesystem for MVP
- MinIO/S3-compatible storage later

## First Migration Tables

| Order | Tables |
|---|---|
| 1 | `organizations`, `users`, `roles`, `permissions`, `organization_members`, `role_permissions` |
| 2 | `audit_logs`, `system_settings` |
| 3 | `llm_providers`, `llm_provider_secrets`, `llm_agent_mappings` |
| 4 | `projects`, `subprojects`, `migration_requirements` |
| 5 | `source_connections`, `target_connections`, `schemas`, `tables`, `columns`, `schema_snapshots` |
| 6 | `agent_definitions`, `agent_tasks`, `agent_outputs`, `prompt_templates`, `prompt_versions`, `workflow_runs`, `workflow_steps` |
| 7 | `code_artifacts`, `code_artifact_versions`, `artifact_dependencies`, `artifact_lineage`, `artifact_approvals` |
| 8 | `code_reviews`, `code_review_comments`, `code_conversion_runs`, `notebook_generation_runs`, `dag_review_runs` |
| 9 | `validation_rules`, `validation_runs`, `validation_results`, `recon_runs`, `recon_results`, `reports`, `report_exports` |
| 10 | `system_health_checks`, `worker_heartbeats`, `failed_jobs` |

## Table Build Order

1. Identity and tenancy
2. Security and audit
3. LLM provider settings
4. Projects and requirements
5. Source/target metadata
6. Agent runtime
7. Artifact metadata
8. Developer execution records
9. Validation/recon/reporting
10. Observability

## Metadata-Only Policy

Store:

- Names, IDs, statuses, paths, hashes, counts, summaries, and timestamps
- Agent outputs and report summaries
- Validation/recon metadata
- Approval history and audit logs

Do not store by default:

- Full source rows
- Raw PII
- Full production exports
- Full API keys
- Full database passwords

## Artifact Metadata

`code_artifacts` should track root artifact metadata. `code_artifact_versions` should track version number, content hashes, generated agent, LLM model/provider metadata, approval status, and storage path/reference.

## Encrypted Secrets

- Store encrypted API keys in dedicated secret tables.
- Track key version and rotation timestamp.
- Return masked display values only.
- Plan future external secret references for Docker secrets, Vault, AWS Secrets Manager, Azure Key Vault, and GCP Secret Manager.

## Audit Logs

Audit records should include:

- `organization_id`
- `actor_id`
- `action`
- `entity_type`
- `entity_id`
- `metadata`
- `ip_address`
- `user_agent`
- `created_at`

Audit logs should be append-only where possible.

## Indexes

Add indexes for:

- `organization_id`
- `project_id`
- `status`
- `created_at`
- `artifact_id, version_number`
- `workflow_run_id, status`
- `provider_id`
- `email`

## Alembic Migration Plan

- Use one migration per coherent feature slice.
- Test upgrades from empty database.
- Test downgrade where practical.
- Do not rewrite merged migration history.
- Seed only system roles, permissions, and agent definitions.

## Related Architecture Docs

| Doc | What it covers |
|---|---|
| `DATABASE_DESIGN.md` | Full table groups, relationships, indexes, encryption, audit log design |
| `README.md 12` | Complete table list (60+ tables) |
| `docs/storage/ARTIFACT_STORAGE.md` | Artifact metadata vs file storage separation |
| `docs/security/SECRETS_MANAGEMENT.md` | Secret encryption, rotation, masking |
| `docs/governance/GOVERNANCE_AUDIT.md` | Audit log design, approval history, agent decision logs |
