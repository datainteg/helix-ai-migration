# Database Design

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

PostgreSQL is the global metadata store for Helix Migration. It stores metadata, workflow state, agent artifacts, validation summaries, reconciliation results, reports, approvals, audit logs, and configuration.

## Design Principle

Store metadata by default, not full production business data.

Examples of metadata:

- Schema names
- Table names
- Column names
- Data types
- Row counts
- Constraints
- Validation status
- Mismatch summaries
- Report metadata

Full customer records should not be stored unless a deployment explicitly enables that behavior.

## Table Groups

| Group | Purpose |
|---|---|
| Identity and tenancy | Users, organizations, roles, permissions |
| Project management | Projects, subprojects, requirements, approvals |
| Connections and metadata | Source/target systems, schemas, tables, columns |
| LLM configuration | Providers, models, agent mappings, encrypted keys |
| Agent runtime | Agent definitions, tasks, outputs, memory, prompts |
| Workflow runtime | Workflow runs, steps, retries, failures |
| Validation | Rules, runs, results, suites |
| Reconciliation | Recon runs, summaries, mismatches |
| Reporting | Reports, exports, attachments metadata |
| Audit | Security, admin, project, and workflow events |

## Suggested Tables

### Identity and Tenancy

| Table | Key fields |
|---|---|
| `organizations` | `id`, `name`, `slug`, `status`, `created_at` |
| `users` | `id`, `email`, `name`, `password_hash`, `status`, `last_login_at` |
| `organization_members` | `id`, `organization_id`, `user_id`, `role_id`, `status` |
| `roles` | `id`, `organization_id`, `name`, `scope`, `is_system` |
| `permissions` | `id`, `code`, `description` |
| `role_permissions` | `id`, `role_id`, `permission_id` |

### Project Management

| Table | Key fields |
|---|---|
| `projects` | `id`, `organization_id`, `name`, `status`, `owner_id`, `risk_level` |
| `subprojects` | `id`, `project_id`, `name`, `migration_domain`, `status` |
| `migration_requirements` | `id`, `project_id`, `source_text`, `status`, `version` |
| `approvals` | `id`, `organization_id`, `project_id`, `subject_type`, `subject_id`, `status`, `approved_by` |

### Connections and Metadata

| Table | Key fields |
|---|---|
| `source_connections` | `id`, `organization_id`, `project_id`, `name`, `connector_type`, `status` |
| `target_connections` | `id`, `organization_id`, `project_id`, `name`, `connector_type`, `status` |
| `connection_secrets` | `id`, `connection_id`, `connection_kind`, `encrypted_payload`, `key_version` |
| `schemas` | `id`, `project_id`, `connection_id`, `name`, `schema_type` |
| `tables` | `id`, `schema_id`, `name`, `row_count`, `metadata_hash` |
| `columns` | `id`, `table_id`, `name`, `data_type`, `nullable`, `ordinal_position` |
| `schema_snapshots` | `id`, `project_id`, `connection_id`, `snapshot_hash`, `captured_at` |

### LLM Configuration

| Table | Key fields |
|---|---|
| `llm_providers` | `id`, `organization_id`, `provider_type`, `name`, `base_url`, `default_model`, `status` |
| `llm_provider_secrets` | `id`, `provider_id`, `encrypted_api_key`, `key_version`, `rotated_at` |
| `llm_agent_mappings` | `id`, `organization_id`, `agent_type`, `provider_id`, `model`, `temperature`, `max_tokens` |

### Agent Runtime

| Table | Key fields |
|---|---|
| `agent_definitions` | `id`, `name`, `agent_type`, `description`, `schema_version` |
| `agent_tasks` | `id`, `project_id`, `agent_type`, `status`, `input_payload`, `started_at`, `finished_at` |
| `agent_outputs` | `id`, `task_id`, `schema_name`, `schema_version`, `output_payload`, `confidence_score` |
| `agent_memory` | `id`, `project_id`, `agent_type`, `memory_type`, `content`, `expires_at` |
| `prompt_templates` | `id`, `name`, `agent_type`, `template`, `status` |
| `prompt_versions` | `id`, `template_id`, `version`, `content`, `created_by` |

### Workflow Runtime

| Table | Key fields |
|---|---|
| `workflow_runs` | `id`, `project_id`, `workflow_type`, `temporal_workflow_id`, `status` |
| `workflow_steps` | `id`, `workflow_run_id`, `step_name`, `agent_task_id`, `status`, `attempt` |
| `workflow_failures` | `id`, `workflow_run_id`, `step_id`, `error_code`, `error_message`, `retryable` |

### Validation and Reconciliation

| Table | Key fields |
|---|---|
| `validation_rules` | `id`, `project_id`, `rule_type`, `target_ref`, `definition`, `status` |
| `validation_runs` | `id`, `project_id`, `started_by`, `status`, `started_at`, `finished_at` |
| `validation_results` | `id`, `run_id`, `rule_id`, `status`, `observed_value`, `expected_value` |
| `recon_runs` | `id`, `project_id`, `source_ref`, `target_ref`, `status` |
| `recon_results` | `id`, `run_id`, `result_type`, `summary`, `mismatch_count`, `details_ref` |

### Reports and Audit

| Table | Key fields |
|---|---|
| `reports` | `id`, `project_id`, `report_type`, `title`, `status`, `storage_ref` |
| `report_exports` | `id`, `report_id`, `format`, `storage_ref`, `created_by` |
| `audit_logs` | `id`, `organization_id`, `actor_id`, `action`, `entity_type`, `entity_id`, `metadata`, `created_at` |
| `system_settings` | `id`, `organization_id`, `key`, `value`, `updated_by` |

## Relationships

- Organization has many users through `organization_members`.
- Organization has many projects.
- Project has many subprojects, connections, schemas, agent tasks, validation runs, recon runs, reports, and approvals.
- Connection has one encrypted secret payload.
- Schema has many tables; table has many columns.
- Workflow run has many workflow steps.
- Agent task has one or more outputs.
- Prompt template has many prompt versions.
- Validation run has many validation results.
- Recon run has many recon results.

## Indexes

Recommended indexes:

- `organization_id` on tenant-owned tables
- `project_id` on project-owned tables
- `email` unique index on `users`
- `slug` unique index on `organizations`
- `status` indexes for active workflow and task queries
- `created_at` indexes for audit and report history
- Composite indexes on `organization_id, created_at`
- Composite indexes on `project_id, status`
- Hash or unique indexes for schema snapshot hashes where useful

## Encryption Strategy

- Store secrets in dedicated secret tables.
- Encrypt API keys, connection passwords, and tokens before writing to PostgreSQL.
- Store masked display values separately or derive them safely.
- Track `key_version` for rotation.
- Never return encrypted payloads to the frontend.
- Never log decrypted secrets.
- Use environment-managed encryption keys in self-hosted deployments.

## Audit Log Design

Audit logs should capture:

- Authentication events
- User and role changes
- Organization changes
- LLM provider create/update/delete/test
- API key rotation
- Connector create/update/delete/test
- Agent workflow start, approval, failure, retry, completion
- Validation and recon execution
- Report export and download

Audit records should include actor, action, entity type, entity ID, organization ID, IP address when available, user agent when available, and timestamp.

## Migration Strategy

- Use Alembic for all database changes.
- Use reviewable migration files.
- Include downgrade logic where practical.
- Do not modify existing migration history after merge.
- Use seed scripts only for system roles, permissions, and agent definitions.
- Test migrations on empty and existing databases.

## Data Not Stored by Default

Do not store:

- Full production table rows
- Sensitive customer documents
- Raw PII values
- Full API keys
- Full database passwords
- Large source exports
- Unmasked connection strings

If a deployment enables sample data storage, it must be explicit, audited, configurable, and documented.

## Developer Execution Tables

The Developer Execution Layer stores metadata for uploaded code, generated draft artifacts, reviews, conversion runs, notebook generation, DAG review, approvals, lineage, and dependencies. PostgreSQL stores metadata and hashes. Actual uploaded/generated files should be stored on the local filesystem for MVP and in MinIO/S3-compatible storage later.

| Table | Purpose | Key fields |
|---|---|---|
| `code_artifacts` | Root record for uploaded or generated code artifacts | `id`, `organization_id`, `project_id`, `subproject_id`, `artifact_name`, `artifact_type`, `source_system`, `target_system`, `storage_path`, `created_by`, `created_at` |
| `code_artifact_versions` | Version history for source and generated artifacts | `id`, `artifact_id`, `version_number`, `source_content_hash`, `generated_content_hash`, `change_summary`, `generated_by_agent`, `llm_provider_id`, `llm_model`, `approval_status`, `created_at` |
| `code_reviews` | AI and human review summary for an artifact version | `id`, `artifact_version_id`, `review_status`, `quality_score`, `risk_score`, `summary`, `created_by_agent`, `created_at` |
| `code_review_comments` | Inline or file-level comments from AI or humans | `id`, `code_review_id`, `artifact_version_id`, `line_start`, `line_end`, `comment_type`, `severity`, `message`, `created_by`, `created_at` |
| `code_conversion_runs` | Tracks source-to-target draft conversion attempts | `id`, `artifact_id`, `source_type`, `target_type`, `status`, `input_version_id`, `output_version_id`, `assumptions`, `limitations`, `created_at` |
| `notebook_generation_runs` | Tracks Databricks notebook draft generation | `id`, `artifact_id`, `input_version_id`, `output_version_id`, `status`, `notebook_format`, `assumptions`, `validation_cells_added`, `created_at` |
| `dag_review_runs` | Stores workflow/DAG review results | `id`, `artifact_id`, `duplicate_task_ids`, `cycles_detected`, `missing_timeouts`, `risky_sensors`, `quality_score`, `report_json`, `created_at` |
| `artifact_approvals` | Human approval or rejection for generated artifacts | `id`, `artifact_version_id`, `organization_id`, `project_id`, `status`, `approved_by`, `decision_notes`, `created_at` |
| `artifact_lineage` | Links source artifacts, generated artifacts, agent outputs, and validation plans | `id`, `source_artifact_version_id`, `target_artifact_version_id`, `agent_task_id`, `validation_plan_id`, `lineage_type`, `created_at` |
| `artifact_dependencies` | Extracted dependencies from uploaded code or DAGs | `id`, `artifact_version_id`, `dependency_name`, `dependency_type`, `dependency_ref`, `is_external`, `created_at` |

Developer artifact rules:

- Store content hashes for uploaded and generated artifacts.
- Store metadata, lineage, summaries, comments, and approvals in PostgreSQL.
- Do not store production business data inside artifact metadata.
- Treat generated code as draft until `artifact_approvals.status` is approved.
- Link generated artifacts to validation and reconciliation plans where applicable.

## Enterprise Supporting Table Groups

PostgreSQL stores metadata. Object/file storage stores actual artifacts. Secrets are encrypted in PostgreSQL for MVP or referenced from external secret managers later. Audit logs should be append-only where possible.

### Artifact Storage Tables

| Table | Purpose | Key fields |
|---|---|---|
| `code_artifacts` | Artifact root metadata | `id`, `organization_id`, `project_id`, `subproject_id`, `artifact_name`, `artifact_type`, `storage_provider`, `storage_path`, `owner_id`, `created_at` |
| `code_artifact_versions` | Version metadata and hashes | `id`, `artifact_id`, `version_number`, `content_hash`, `generated_content_hash`, `approval_status`, `created_at` |
| `artifact_dependencies` | Extracted dependencies | `id`, `artifact_version_id`, `dependency_name`, `dependency_type`, `dependency_ref`, `is_external` |
| `artifact_lineage` | Source-to-generated lineage | `id`, `source_artifact_version_id`, `target_artifact_version_id`, `agent_task_id`, `validation_plan_id` |
| `artifact_storage_locations` | Storage provider config metadata | `id`, `organization_id`, `provider_type`, `base_path`, `bucket`, `status` |

### Developer Execution Tables

| Table | Purpose | Key fields |
|---|---|---|
| `code_reviews` | Review summary | `id`, `artifact_version_id`, `review_status`, `quality_score`, `risk_score`, `summary` |
| `code_review_comments` | Inline/file comments | `id`, `code_review_id`, `line_start`, `line_end`, `severity`, `message` |
| `code_conversion_runs` | Draft conversion lifecycle | `id`, `artifact_id`, `source_type`, `target_type`, `status`, `input_version_id`, `output_version_id`, `assumptions`, `limitations` |
| `notebook_generation_runs` | Notebook draft generation | `id`, `artifact_id`, `input_version_id`, `output_version_id`, `status`, `notebook_format` |
| `dag_review_runs` | DAG/workflow review | `id`, `artifact_id`, `duplicate_task_ids`, `cycles_detected`, `missing_timeouts`, `risky_sensors`, `quality_score`, `report_json` |
| `artifact_approvals` | Human artifact decisions | `id`, `artifact_version_id`, `status`, `approved_by`, `decision_notes`, `created_at` |

### Governance Tables

| Table | Purpose | Key fields |
|---|---|---|
| `audit_logs` | Append-only platform actions | `id`, `organization_id`, `actor_id`, `action`, `entity_type`, `entity_id`, `metadata`, `created_at` |
| `agent_decision_logs` | Agent decision trace | `id`, `agent_task_id`, `decision_type`, `reasoning_summary`, `confidence_score`, `created_at` |
| `approval_history` | Approval lifecycle history | `id`, `subject_type`, `subject_id`, `status`, `actor_id`, `notes`, `created_at` |
| `prompt_execution_logs` | Prompt/model invocation metadata | `id`, `prompt_version_id`, `agent_task_id`, `llm_provider_id`, `model`, `status` |
| `llm_usage_logs` | Token and latency tracking | `id`, `organization_id`, `agent_type`, `provider_id`, `model`, `input_tokens`, `output_tokens`, `latency_ms` |
| `data_access_logs` | Access to metadata/artifacts/reports | `id`, `organization_id`, `actor_id`, `resource_type`, `resource_id`, `access_type`, `created_at` |

### Observability Tables

| Table | Purpose | Key fields |
|---|---|---|
| `system_health_checks` | System health snapshots | `id`, `component`, `status`, `latency_ms`, `details`, `created_at` |
| `worker_heartbeats` | Worker liveness | `id`, `worker_id`, `queue_name`, `status`, `last_seen_at` |
| `workflow_execution_logs` | Temporal/workflow events | `id`, `workflow_run_id`, `event_type`, `status`, `details`, `created_at` |
| `failed_jobs` | Failed task registry | `id`, `job_type`, `subject_id`, `error_code`, `error_message`, `retryable`, `created_at` |
| `connector_health_checks` | Connector availability | `id`, `connection_id`, `status`, `latency_ms`, `error_message`, `checked_at` |
| `validation_job_metrics` | Validation runtime metrics | `id`, `validation_run_id`, `duration_ms`, `records_checked`, `failed_checks`, `created_at` |

### Template Tables

| Table | Purpose | Key fields |
|---|---|---|
| `migration_templates` | Migration project templates | `id`, `name`, `source_type`, `target_type`, `template_path`, `status` |
| `validation_templates` | Reusable validation templates | `id`, `name`, `rule_set`, `template_path`, `status` |
| `agent_workflow_templates` | Agent workflow templates | `id`, `name`, `workflow_type`, `template_path`, `status` |
| `code_conversion_templates` | Code conversion patterns | `id`, `source_type`, `target_type`, `template_path`, `status` |
| `report_templates` | Report export templates | `id`, `report_type`, `format`, `template_path`, `status` |

### Memory Tables

| Table | Purpose | Key fields |
|---|---|---|
| `project_memory` | Project-scoped reusable context | `id`, `project_id`, `memory_type`, `content`, `created_at` |
| `organization_memory` | Organization standards | `id`, `organization_id`, `memory_type`, `content`, `created_at` |
| `reusable_validation_rules` | Approved validation rules | `id`, `organization_id`, `name`, `definition`, `status` |
| `approved_patterns` | Approved migration/code patterns | `id`, `organization_id`, `pattern_type`, `summary`, `content_ref` |
| `knowledge_entries` | Searchable knowledge records | `id`, `organization_id`, `source_type`, `title`, `content_ref`, `tags` |

MVP memory should use PostgreSQL-backed project and organization memory only. Full vector memory and large-scale retrieval are future scope.

### Plugin, Secret, Notification, and Import/Export Tables

| Group | Tables |
|---|---|
| Plugins | `plugin_registry`, `plugin_versions`, `plugin_settings` |
| Secrets | `secret_references`, `encrypted_secrets`, `secret_rotation_logs` |
| Notifications | `notification_channels`, `notification_rules`, `notification_events`, `notification_delivery_logs`, `smtp_settings` |
| Import / Export | `export_jobs`, `import_jobs`, `exported_artifacts`, `export_templates` |

Notification settings should include `smtp_settings` for admin-managed email delivery metadata. Key fields: `id`, `organization_id`, `host`, `port`, `username`, `encrypted_password` or `secret_reference_id`, `from_email`, `from_name`, `use_tls`, `use_starttls`, `status`, `last_tested_at`, `created_by`, `updated_at`. SMTP secrets must be encrypted or externally referenced and masked in all API responses.
