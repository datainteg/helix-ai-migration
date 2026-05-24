# Architecture

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

Helix Migration is an open-source, self-hosted enterprise migration command center. It combines a Next.js frontend, FastAPI backend, PostgreSQL metadata store, Redis, Temporal OSS, agent runtime, validation and reconciliation engine, connector framework, and LLM router.

> **Reality note (2026-05-23):** This document describes the **target** architecture. Several layers are partial or stubbed in the current codebase: BMAD nodes don't yet call LLMs, validation/reconciliation API endpoints return hardcoded fixtures, the worker Docker image fails to build, and 4 of 8 connectors are skeletons. See [README.md → Honest Capability Matrix](README.md#honest-capability-matrix) for the implemented-vs-aspirational breakdown and [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md) for the prioritized engineering plan.

## High-Level Architecture

```text
Users
  |
  v
Frontend UI
Next.js + TypeScript + Tailwind CSS + shadcn/ui + React Flow + Framer Motion
  |
  v
Backend API
FastAPI + Pydantic + SQLAlchemy/SQLModel
  |
  +--> PostgreSQL Global Metadata Store
  |      users, orgs, projects, metadata, prompts, agent outputs, reports, audit logs
  |
  +--> Redis
  |      cache, short-lived state, rate limits, lightweight queues
  |
  +--> Temporal OSS
  |      durable workflows, retries, long-running orchestration
  |
  +--> Agent Runtime
  |      BMAD + LangGraph + PydanticAI + LLM Router
  |
  +--> Validation and Recon Engine
  |      Great Expectations, Soda Core, dbt tests, custom checks
  |
  +--> Connector Framework
         databases, warehouses, files, APIs, cloud storage, ETL systems
```

## Frontend Layer

The frontend provides:

- Admin panel
- Business dashboard
- Engineering dashboard
- Project workspace
- Agent workflow canvas
- Connector hub
- Metadata explorer
- Validation center
- Reconciliation reports
- Report center
- Audit log viewer
- LLM provider settings

React Flow should be used for workflow and lineage views. shadcn/ui should provide accessible enterprise components. Framer Motion should be used for subtle transitions, not distracting effects.

## Backend API Layer

The backend owns:

- Authentication and authorization
- RBAC enforcement
- Organization separation
- Project and subproject APIs
- Metadata APIs
- LLM provider APIs
- Agent task APIs
- Validation and reconciliation APIs
- Report APIs
- Audit APIs
- Admin and system health APIs

FastAPI should expose OpenAPI documentation and use Pydantic models for all request and response contracts.

## PostgreSQL Metadata Layer

PostgreSQL is the global metadata store. It stores platform metadata and workflow artifacts, not full customer business data by default.

Stored data includes:

- Users and organizations
- Roles and permissions
- Projects and subprojects
- Source and target system metadata
- Schemas, tables, columns, and snapshots
- Agent tasks and outputs
- Prompt templates and versions
- Validation rules and results
- Reconciliation results
- Reports and approvals
- Audit logs
- LLM provider settings

## Redis Layer

Redis supports:

- Short-lived cache
- Request rate limiting
- Temporary workflow state
- Session support when needed
- Lightweight queue patterns where Temporal is not required

Redis should not be the source of truth for durable workflow or audit data.

## Temporal Workflow Layer

Temporal OSS provides durable execution for:

- Agent planning workflows
- Connector scans
- Schema comparison jobs
- Validation runs
- Reconciliation runs
- Report generation
- Long-running retries

Temporal workflows should store final state and user-visible artifacts in PostgreSQL.

## Agent Runtime Layer

Agent runtime uses:

| Component | Role |
|---|---|
| BMAD | Migration methodology |
| LangGraph | Agent graph and state transitions |
| PydanticAI | Structured output validation |
| LLM Router | Provider/model routing |
| Temporal | Durable execution |
| PostgreSQL | Output, prompt, approval, and audit persistence |

Agent outputs must be typed, validated, versioned, and stored.

## Validation and Recon Engine

Validation and reconciliation combine:

- Great Expectations for data quality suites
- Soda Core for operational data quality checks
- dbt tests for SQL-based validation
- Custom reconciliation engine for counts, checksums, mismatches, and summary reports

The engine should store metadata, results, summaries, and report artifacts. It should avoid storing full source or target data by default.

## Connector Framework

Connectors should support:

- Test connection
- Metadata extraction
- Schema scan
- Table and column profiling
- Row count
- Optional sample preview only when configured

Connector secrets must be encrypted and masked.

## LLM Router

The LLM router provides a single backend abstraction for:

- OpenAI / ChatGPT
- Google Gemini
- Anthropic Claude
- DeepSeek
- OpenRouter
- Custom OpenAI-compatible APIs
- Local model URLs
- Future Ollama, vLLM, and LM Studio support

The router must support default model mode and agent-wise model mapping.

## Admin Panel Architecture

Admin features:

```text
Admin Panel
  |-- User Management
  |-- Role Management
  |-- Organization Settings
  |-- LLM Provider Settings
  |-- Custom Model URL Settings
  |-- Agent Model Mapping
  |-- Connector Management
  |-- Prompt Template Management
  |-- Workflow Settings
  |-- Audit Logs
  |-- System Health
  |-- Security Settings
```

RBAC must control both frontend visibility and backend authorization.

## Deployment Architecture

Docker Compose should run:

```text
helix-ai-migration-frontend
helix-ai-migration-backend
helix-ai-migration-worker
postgres
redis
temporal
temporal-ui
```

The official images are:

- `datainteg/helix-ai-migration-frontend`
- `datainteg/helix-ai-migration-backend`
- `datainteg/helix-ai-migration-worker`

## Future Kubernetes Architecture

Future Helm chart should include:

- Frontend deployment and service
- Backend deployment and service
- Worker deployment with scalable replicas
- PostgreSQL dependency or external database configuration
- Redis dependency or external Redis configuration
- Temporal dependency or external Temporal configuration
- Secret management integration
- Ingress and TLS configuration
- Horizontal scaling for backend and workers

## Developer Execution Layer

Helix Migration has a Management Layer and a Developer Execution Layer.

| Layer | Product areas |
|---|---|
| Management Layer | Dashboard, projects, subprojects, agents, validation, reconciliation, reports, approvals, admin panel, LLM settings |
| Developer Execution Layer | Developer Workspace, Code Review Center, ETL Migration Workspace, DAG / Workflow Analyzer, side-by-side diffs, artifact versioning, generated-code approvals |

Developer execution architecture:

```text
Frontend
  -> Developer Workspace UI
  -> Code Review Center
  -> Backend API
  -> Artifact Storage Metadata
  -> Agent Runtime
  -> Code Analyzer / Review / Migration Agents
  -> Versioned Artifact Store
  -> Human Approval
  -> Reports
```

The Developer Workspace lets engineers upload `.py`, `.sql`, `.ipynb`, DAG files, and config files for AI-assisted analysis, review, draft conversion, notebook generation, and approval. Helix Migration generates draft migration code, notebook structures, validation plans, and reconciliation reports that must be reviewed and approved by humans before production use.

PostgreSQL stores artifact metadata, artifact versions, content hashes, review records, conversion run metadata, lineage, dependencies, approvals, and links to agent outputs. Actual uploaded files and generated artifact contents should be stored on the local filesystem for MVP and in MinIO/S3-compatible storage later, while PostgreSQL remains the metadata source of truth.

Developer-focused agents include:

- Code Analyzer Agent
- Code Review Agent
- Code Migration Agent
- Notebook Generator Agent
- DAG / Workflow Review Agent
- Version Control Agent

## Final Layered Architecture

```text
Helix Migration Platform
├── UI / Experience Layer
├── Management Layer
├── Developer Execution Layer
├── Agent Runtime Layer
├── Workflow Orchestration Layer
├── Connector Layer
├── Validation & Reconciliation Layer
├── Metadata & Storage Layer
├── Artifact Storage Layer
├── Governance & Audit Layer
├── Observability Layer
├── Template Layer
├── Knowledge & Memory Layer
├── Plugin / Extension Layer
├── Secrets Management Layer
├── Notification Layer
├── Import / Export Layer
├── Safe Execution Layer
└── Deployment Layer
```

| Layer | Responsibility |
|---|---|
| UI / Experience Layer | Next.js experience for business users, engineers, admins, and reviewers |
| Management Layer | Dashboard, projects, subprojects, agents, validation, reconciliation, reports, approvals, admin panel, LLM settings, governance, observability |
| Developer Execution Layer | Code Review Center, ETL Migration Workspace, DAG analyzer, diff viewer, notebook generator, artifact versioning, generated-code approvals |
| Agent Runtime Layer | BMAD agents, developer agents, typed PydanticAI outputs, LLM Router |
| Workflow Orchestration Layer | Temporal OSS workflows, retries, long-running jobs, human approval waits |
| Connector Layer | Metadata extraction, schema scans, connector health, future plugin connectors |
| Validation & Reconciliation Layer | Great Expectations, Soda Core, dbt tests, custom reconciliation engine |
| Metadata & Storage Layer | PostgreSQL global metadata store for tenants, projects, workflow state, logs, and artifact metadata |
| Artifact Storage Layer | Local filesystem for MVP, MinIO/S3-compatible storage later for uploaded/generated files |
| Governance & Audit Layer | User activity, approvals, agent decisions, prompt history, LLM usage, data access, exportable audits |
| Observability Layer | System health, worker heartbeats, Temporal status, failed jobs, token usage, latency, connector status |
| Template Layer | Static JSON/YAML templates for MVP, managed template library later |
| Knowledge & Memory Layer | Project memory, organization memory, approved patterns, reusable validation rules |
| Plugin / Extension Layer | Custom connectors, validation rules, agents, templates, report formats, LLM providers |
| Secrets Management Layer | Encrypted DB secrets for MVP, Docker secrets/Vault/cloud secret managers later |
| Notification Layer | Email, Slack, Teams, approval reminders, validation alerts, agent completion alerts |
| Import / Export Layer | PDF, Markdown, JSON, CSV, HTML, project config, reports, agent outputs, templates |
| Safe Execution Layer | Analysis-only MVP; future sandboxed execution with isolated containers and resource limits |
| Deployment Layer | Docker Compose for MVP, future Helm chart |

Management flow:

```text
Create Project
  -> Add Requirement
  -> BMAD Agents
  -> Architecture Plan
  -> Validation Plan
  -> Human Approval
  -> Recon Setup
  -> Reports
  -> Audit Trail
```

Developer execution flow:

```text
Upload Code
  -> Artifact Storage
  -> Metadata Registration
  -> Code Analyzer Agent
  -> Code Review Agent
  -> Code Migration Agent
  -> Notebook Generator Agent, if required
  -> Side-by-side Diff
  -> Human Approval
  -> Version Control Agent
  -> Validation Plan Link
  -> Report Export
```

Helix Migration generates draft migration code, notebook structures, validation plans, and reconciliation reports that must be reviewed and approved by humans before production use. MVP must not execute arbitrary uploaded code.

## Related Deep-Dive Docs

| Layer | Docs |
|---|---|
| UI / Experience | `UI_UX_GUIDE.md`, `docs/frontend/FRONTEND_GUIDE.md` |
| Management | `README.md 8–9`, `docs/project-planning/PROJECT_PLAN.md` |
| Developer Execution | `docs/developer-workspace/DEVELOPER_WORKSPACE.md`, `docs/developer-workspace/CODE_REVIEW_CENTER.md`, `docs/developer-workspace/ETL_MIGRATION_WORKSPACE.md` |
| Agent Runtime | `AGENT_WORKFLOW.md`, `docs/agents/AGENT_RUNTIME_GUIDE.md`, `docs/agents/LLM_ROUTER.md`, `docs/agents/PROMPT_ENGINEERING.md` |
| Workflow Orchestration | `DOCKER_GUIDE.md` (Temporal section) |
| Connector | `docs/connectors/CONNECTOR_GUIDE.md` |
| Validation & Recon | `docs/validation/VALIDATION_RECON_GUIDE.md` |
| Metadata & Storage | `DATABASE_DESIGN.md`, `docs/storage/ARTIFACT_STORAGE.md` |
| Governance & Audit | `docs/governance/GOVERNANCE_AUDIT.md` |
| Observability | `docs/observability/OBSERVABILITY.md` |
| Templates | `docs/templates/TEMPLATE_SYSTEM.md` |
| Knowledge & Memory | `docs/knowledge/KNOWLEDGE_MEMORY.md` |
| Plugins | `docs/plugins/PLUGIN_SYSTEM.md` |
| Secrets Management | `docs/security/SECRETS_MANAGEMENT.md`, `SECURITY.md` |
| Notifications | `docs/notifications/NOTIFICATION_SYSTEM.md` |
| Import / Export | `docs/import-export/IMPORT_EXPORT.md` |
| Safe Execution | `docs/security/SAFE_EXECUTION.md` |
| Deployment | `docs/deployment/INSTALLATION.md`, `DOCKER_GUIDE.md` |
| API | `API_DESIGN.md` |
| Testing | `TESTING.md` |
| Operations | `docs/operations/BACKUP_RESTORE.md`, `docs/operations/CI_CD.md` |
