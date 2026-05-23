# Helix Migration

**Open-source AI-powered migration and validation platform.**

Helix Migration is a self-hosted, open-source AI migration platform that helps enterprises plan, validate, reconcile, and manage complex data migrations using intelligent multi-agent workflows.

> **Website:** `https://helix.datainteg.io`  
> **GitHub:** `https://github.com/datainteg/helix-ai-migration`  
> **Docker Images:**
>
> - `datainteg/helix-ai-migration-frontend`
> - `datainteg/helix-ai-migration-backend`
> - `datainteg/helix-ai-migration-worker`

---

## 1. Why Helix Migration?

Enterprise migration projects are difficult because they are not only about moving data from one system to another.

They require:

- Requirement understanding
- Architecture planning
- Source and target discovery
- Schema comparison
- Mapping design
- Validation planning
- Reconciliation reports
- Cutover planning
- Rollback strategy
- Auditability
- Human approvals
- Clear dashboards for business and technical users

Most teams manage these activities using spreadsheets, documents, SQL scripts, manual checks, and scattered communication.

Helix Migration brings these workflows into one open-source platform.

The goal is to create an enterprise-grade migration command center where users can:

- Create migration projects and subprojects
- Configure source and target systems
- Use AI agents for planning and documentation
- Store global metadata in PostgreSQL
- Generate migration architecture and validation plans
- Run validation and reconciliation checks
- Track agent progress, risks, approvals, and reports
- Configure their own LLM keys or custom model URLs
- Deploy everything using Docker Compose

---

## 2. Product Identity

```text
Brand/Product: Helix Migration
Repository: helix-ai-migration
Website: helix.datainteg.io
Tagline: Open-source AI-powered migration and validation platform.
```

Official one-line description:

```text
Helix Migration is an open-source AI-powered migration and validation platform that helps enterprises plan, validate, reconcile, and manage complex data migrations using intelligent multi-agent workflows.
```

---

## 3. Core Positioning

Helix Migration is not just a chatbot.

It is an open-source, self-hosted enterprise platform for:

- AI-assisted migration planning
- Multi-agent workflow orchestration
- Source-to-target metadata management
- Validation rule generation
- Reconciliation reporting
- Human approval workflows
- Migration governance
- Enterprise dashboards

Think of it as:

```text
Airbyte-style connectors
+ Databricks-style workspace
+ Apache Ranger/Hue-style admin experience
+ AI agents
+ Validation and reconciliation engine
```

---

## 4. High-Level Architecture

```text
Frontend UI
Next.js + Tailwind CSS + shadcn/ui + React Flow
        ↓
Backend API
FastAPI
        ↓
PostgreSQL Global Metadata Store
Users, projects, schemas, agents, prompts, reports, validation results
        ↓
Agent Runtime
BMAD Methodology + LangGraph + PydanticAI
        ↓
Workflow Runtime
Temporal OSS
        ↓
Validation & Recon Engine
Schema checks, row counts, null checks, duplicate checks, mismatch reports
        ↓
LLM Router
OpenAI, Claude, Gemini, DeepSeek, OpenRouter, custom/local model URL
        ↓
Source & Target Connectors
Databases, warehouses, files, APIs, cloud storage, ETL systems
```

---

## 5. Recommended Technology Stack

### Frontend

| Component | Purpose |
|---|---|
| Next.js | Main web application |
| TypeScript | Type-safe frontend development |
| Tailwind CSS | Utility-first styling |
| shadcn/ui | Enterprise-grade UI components |
| React Flow | Agent workflow and lineage visualization |
| Framer Motion | Smooth UI animations |
| Zustand / TanStack Query | State and API management |

### Backend

| Component | Purpose |
|---|---|
| FastAPI | Backend API service |
| Python | Main backend and agent runtime language |
| PostgreSQL | Global metadata database |
| Redis | Cache, queue, temporary state |
| Temporal OSS | Durable workflow orchestration |
| SQLAlchemy / SQLModel | Database ORM |
| Alembic | Database migrations |
| Pydantic | Request/response validation |

### Agent Runtime

| Component | Purpose |
|---|---|
| BMAD | Migration workflow methodology |
| LangGraph | Multi-agent graph orchestration |
| PydanticAI | Structured AI output validation |
| LLM Router | Provider and model routing layer |
| Prompt Registry | Prompt templates and versions |
| Memory Manager | Short-term and long-term context handling |

### Validation & Recon

| Component | Purpose |
|---|---|
| Great Expectations | Data quality validation |
| Soda Core | Data quality checks |
| dbt tests | SQL-based validation tests |
| Custom Recon Engine | Row counts, checksums, mismatch summaries |

### Deployment

| Component | Purpose |
|---|---|
| Docker | Containerization |
| Docker Compose | One-command local/self-hosted installation |
| Nginx | Optional reverse proxy |
| Helm | Future Kubernetes deployment |

---

## 6. Agent Strategy

Helix Migration uses BMAD (Business, Mission, Architecture, Design) as the default migration methodology — a structured planning lifecycle that guides migrations from requirement understanding through architecture, engineering, validation, and cutover. The platform should not be tightly coupled only to BMAD and should support other workflow templates in the future.

Recommended design:

```text
Helix Agent Runtime
    ↓
Workflow Templates
    ↓
BMAD Migration Workflow
    ↓
Migration-Specific Agents
```

### Why this approach?

- BMAD gives a clear planning lifecycle
- LangGraph manages agent communication and state
- PydanticAI validates structured outputs
- Temporal handles durable workflow execution and retries
- PostgreSQL stores all outputs, prompts, approvals, and metadata

### Core Agents (13 BMAD Skills)

| Agent Key | BMAD Name | Title | Phase | Status |
|---|---|---|---|---|
| `business_analyst` | **Mary** | Business Analyst | Analysis | ✅ Wired into graph |
| `tech_writer` | **Paige** | Technical Writer | Analysis | 🔜 Ready |
| `pm` | **John** | Product Manager | Plan-Workflows | 🔜 Ready |
| `ux_designer` | **Sally** | UX Designer | Plan-Workflows | 🔜 Ready |
| `architect` | **Winston** | System Architect | Solutioning | ✅ Wired into graph |
| `data_engineer` | **Amelia** | Sr. Software Engineer | Implementation | 🔜 Ready |
| `qa_validation` | **QA Bot** | QA Automation Engineer | Implementation | 🔜 Ready |
| `recon` | **Code Reviewer** | Elite Code Reviewer | Implementation | 🔜 Ready |
| `devops` | **DevOps Bot** | DevOps Engineer | Implementation | 🔜 Ready |

**Core Skills:**
| `party_mode` 🎉 | Multi-Agent Orchestrator | Spawns agents as independent subagents |
| `brainstorming` | Creative Ideation | Interactive brainstorming sessions |
| `distillator` | Document Compression | Lossless LLM-optimized compression |
| `advanced_elicitation` | Deep Critique | Socratic, first-principles, red-team methods |

**Current graph:** `START → Mary (BA) → Winston (Architect) → VP → Approval → END`

**Agents reference:** `agents/bmad/official_agents.py` — all 13 agents load from the vendored BMAD-METHOD skill files.

### Agent Communication Flow

```text
User Requirement
    ↓
Business Analyst Agent
    ↓
Architect Agent
    ↓
Human Approval
    ↓
Data Engineer Agent
    ↓
QA / Validation Agent
    ↓
Recon Agent
    ↓
DevOps Agent
    ↓
PM Agent
    ↓
Final Review & Sign-off
```

---

## 7. LLM Provider Management

Helix Migration should support Bring Your Own Key architecture.

Admins can configure LLM providers from the admin panel.

### Supported Providers

- OpenAI / ChatGPT
- Google Gemini
- Anthropic Claude
- DeepSeek
- OpenRouter
- Custom OpenAI-compatible API
- Local model URL
- Ollama / vLLM / LM Studio support in future

### AI Model Settings

Admin should be able to configure:

- Provider name
- API key
- Base URL
- Default model
- Temperature
- Max tokens
- Timeout
- Active/inactive status
- Test connection
- Key rotation
- Masked key display

### Agent-wise Model Mapping

Helix Migration should allow two modes.

#### Simple Mode

Use one default model for all agents.

```text
All Agents → GPT-4.1 / Claude / Gemini / DeepSeek / Local Model
```

#### Advanced Mode

Use different models for different agents.

```text
BA Agent           → Claude
Architect Agent    → GPT
Data Engineer      → DeepSeek
QA Agent           → GPT
Recon Agent        → Gemini
DevOps Agent       → DeepSeek
PM Agent           → Claude
```

This gives users flexibility and helps reduce cost.

---

## 8. Admin Panel

Helix Migration should include a full admin experience similar to enterprise tools such as Apache Ranger, Hue, Airbyte, and Databricks.

### Admin Features

```text
Admin Panel
├── User Management
├── Role Management
├── Organization Settings
├── LLM Provider Settings
├── Custom Model URL Settings
├── Agent Model Mapping
├── Connector Management
├── Prompt Template Management
├── Workflow Settings
├── Audit Logs
├── System Health
├── Docker/System Info
└── Security Settings
```

### User Roles

```text
Super Admin
Admin
Project Manager
Architect
Data Engineer
QA Engineer
Viewer
```

### Security Best Practices

- Encrypt API keys before storing
- Never show full API keys after saving
- Mask keys in the UI
- Support key rotation
- Maintain audit logs
- Use RBAC for admin features
- Support organization-level isolation
- Do not store full business data unless explicitly required

---

## 9. User Experience Strategy

Helix Migration should serve two types of users:

### Business / Client Users

They need:

- Simple dashboards
- Migration progress
- Risk score
- Validation status
- Recon summary
- Approval center
- Downloadable reports
- Minimal technical complexity

### Developer / Engineering Users

They need:

- Source and target schemas
- Mapping logic
- SQL validations
- Agent outputs
- Logs
- Connector debugging
- Recon details
- Workflow traces

Recommended UI concept:

```text
Business Mode   → Simple, visual, executive-friendly
Engineering Mode → Advanced, technical, debuggable
```

---

## 10. Figma-First Design Plan

Before coding the UI, create a complete Figma design system.

### Figma Structure

```text
01_Foundations
02_Design_System
03_Components
04_Landing_Page
05_Admin_Panel
06_Main_Dashboard
07_Project_Workspace
08_Agent_Workflow
09_Connector_Hub
10_Validation_Center
11_Recon_Report
12_Settings
13_Developer_Mode
```

### Required Screens

- Landing page
- Login
- Setup wizard
- Admin dashboard
- LLM settings
- User management
- Main dashboard
- Project creation
- Requirement intake
- Agent workspace
- Agent workflow canvas
- Source/target connector setup
- Schema metadata viewer
- Validation center
- Recon report screen
- Report center
- Audit logs
- System health

### UI Inspiration

- Databricks
- Airbyte
- Apache Superset
- Apache Ranger
- Hue
- Linear
- Vercel
- Cursor
- GitHub Projects
- Temporal UI

Important UX principle:

```text
Complex backend, simple frontend.
```

---

## 11. PostgreSQL Global Metadata Store

PostgreSQL should be used as the global metadata database.

### What to Store

- Users
- Organizations
- Roles
- Projects
- Subprojects
- Source systems
- Target systems
- Connection metadata
- Schema metadata
- Table metadata
- Column metadata
- Agent tasks
- Agent outputs
- Prompt versions
- Agent memory
- Validation rules
- Validation results
- Recon results
- Reports
- Approvals
- Audit logs
- LLM provider settings

### What Not to Store by Default

Avoid storing full customer business data.

Store metadata and summaries only:

- Schema names
- Table names
- Column names
- Data types
- Row counts
- Validation status
- Mismatch summaries
- Report metadata

This makes the platform safer for enterprise and self-hosted usage.

---

## 12. Suggested Database Tables

```text
users
organizations
organization_members
roles
permissions
projects
subprojects
source_connections
target_connections
connection_secrets
schemas
tables
columns
schema_snapshots
migration_requirements
agent_definitions
agent_tasks
agent_outputs
agent_memory
prompt_templates
prompt_versions
llm_providers
llm_agent_mappings
validation_rules
validation_runs
validation_results
recon_runs
recon_results
reports
approvals
audit_logs
workflow_runs
workflow_steps
system_settings
role_permissions
llm_provider_secrets
workflow_failures
report_exports
code_artifacts
code_artifact_versions
artifact_storage_locations
artifact_dependencies
artifact_lineage
code_reviews
code_review_comments
code_conversion_runs
notebook_generation_runs
dag_review_runs
artifact_approvals
agent_decision_logs
prompt_execution_logs
llm_usage_logs
system_health_checks
worker_heartbeats
failed_jobs
connector_health_checks
validation_job_metrics
secret_references
encrypted_secrets
smtp_settings
export_jobs
import_jobs
```

---

## 13. Repository Structure

Recommended repository structure:

```text
helix-ai-migration/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── features/
│   ├── lib/
│   ├── styles/
│   ├── public/
│   ├── Dockerfile
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── auth/
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── worker/
│   ├── workflows/
│   ├── activities/
│   ├── tasks/
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── agents/
│   ├── runtime/
│   ├── bmad/
│   ├── ba_agent/
│   ├── architect_agent/
│   ├── data_engineer_agent/
│   ├── validation_agent/
│   ├── recon_agent/
│   ├── devops_agent/
│   ├── pm_agent/
│   └── schemas/
│
├── connectors/
│   ├── base/
│   ├── postgres/
│   ├── mysql/
│   ├── oracle/
│   ├── sqlserver/
│   ├── snowflake/
│   ├── mongodb/
│   ├── s3/
│   ├── databricks/
│   └── files/
│
├── validation-engine/
│   ├── schema_compare/
│   ├── row_count/
│   ├── null_check/
│   ├── duplicate_check/
│   ├── distribution_check/
│   ├── checksum/
│   └── reports/
│
├── docs/
│   ├── architecture/
│   ├── installation/
│   ├── admin-guide/
│   ├── user-guide/
│   ├── agents/
│   ├── connectors/
│   ├── validation/
│   └── roadmap/
│
├── deployment/
│   ├── docker/
│   ├── nginx/
│   └── helm/
│
├── examples/
│   ├── sample-projects/
│   ├── sample-schemas/
│   └── sample-reports/
│
├── .github/
│   ├── workflows/
│   └── ISSUE_TEMPLATE/
│
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── README.md
├── CONTRIBUTING.md
├── LICENSE
├── SECURITY.md
└── ROADMAP.md
```

---

## 14. Docker Image Strategy

Use multiple Docker images for production, but make installation simple through Docker Compose.

### Official Docker Images

```text
datainteg/helix-ai-migration-frontend
datainteg/helix-ai-migration-backend
datainteg/helix-ai-migration-worker
```

### Required Supporting Services

```text
postgres
redis
temporal
temporal-ui
```

### Why Multiple Images?

Multiple images are better for enterprise because:

- Frontend can scale separately
- Backend can scale separately
- Workers can scale separately
- Failures are isolated
- Logs are easier to debug
- Updates are easier
- Kubernetes deployment becomes easier later

Example scale command:

```bash
docker compose up -d --scale helix-ai-migration-worker=3
```

---

## 15. Docker Compose Plan

Example `docker-compose.yml`:

```yaml
services:
  helix-ai-migration-frontend:
    image: datainteg/helix-ai-migration-frontend:latest
    container_name: helix-ai-migration-frontend
    ports:
      - "8080:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    depends_on:
      - helix-ai-migration-backend

  helix-ai-migration-backend:
    image: datainteg/helix-ai-migration-backend:latest
    container_name: helix-ai-migration-backend
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - postgres
      - redis
      - temporal

  helix-ai-migration-worker:
    image: datainteg/helix-ai-migration-worker:latest
    container_name: helix-ai-migration-worker
    env_file:
      - .env
    depends_on:
      - helix-ai-migration-backend
      - postgres
      - redis
      - temporal

  postgres:
    image: postgres:16
    container_name: helix-postgres
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: helix
      POSTGRES_PASSWORD: helix_password
      POSTGRES_DB: helix_metadata
    volumes:
      - helix_postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    container_name: helix-redis
    ports:
      - "6379:6379"

  temporal:
    image: temporalio/auto-setup:latest
    container_name: helix-temporal
    ports:
      - "7233:7233"
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=helix
      - POSTGRES_PWD=helix_password
      - POSTGRES_SEEDS=postgres
    depends_on:
      - postgres

  temporal-ui:
    image: temporalio/ui:latest
    container_name: helix-temporal-ui
    ports:
      - "8233:8080"
    environment:
      - TEMPORAL_ADDRESS=temporal:7233
    depends_on:
      - temporal

volumes:
  helix_postgres_data:
```

> Note: In production, use secure passwords, secrets management, TLS, and private networking.

---

## 16. Environment Configuration

Example `.env.example`:

```bash
# Application
APP_NAME=Helix Migration
APP_ENV=development
APP_SECRET_KEY=change_me

# Backend
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# Database
DATABASE_URL=postgresql://helix:helix_password@postgres:5432/helix_metadata

# Redis
REDIS_URL=redis://redis:6379/0

# Temporal
TEMPORAL_ADDRESS=temporal:7233
TEMPORAL_NAMESPACE=default

# Security
JWT_SECRET_KEY=change_me
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
ENCRYPTION_KEY=change_me_32_byte_key

# LLM Defaults
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4.1

# Optional Provider Keys
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_GEMINI_API_KEY=
DEEPSEEK_API_KEY=
OPENROUTER_API_KEY=
CUSTOM_LLM_BASE_URL=
CUSTOM_LLM_API_KEY=
```

---

## 17. Installation

### Prerequisites

- Docker
- Docker Compose
- Git

### Quick Start

```bash
git clone https://github.com/datainteg/helix-ai-migration.git
cd helix-ai-migration
cp .env.example .env
docker compose up -d
```

Open the application:

```text
Frontend:    http://localhost:8080
Backend API: http://localhost:8000
Temporal UI: http://localhost:8233
```

### First-Time Setup

1. Open `http://localhost:8080`
2. Create the first admin account
3. Add LLM provider keys
4. Select default model
5. Create organization
6. Create first migration project
7. Add requirement
8. Run AI planning workflow
9. Review generated plan
10. Approve and continue to validation/recon setup

---

## 18. MVP Execution Roadmap

### MVP Phase 1 — Foundation

Goal: Build the installable open-source platform skeleton.

Features:

- GitHub repo structure
- Docker Compose setup
- Frontend shell
- Backend API shell
- PostgreSQL metadata database
- Redis integration
- Basic authentication
- Admin user creation
- Organization setup
- Project creation
- Basic dashboard

Deliverables:

- Running app with Docker Compose
- Admin login
- Project dashboard
- PostgreSQL metadata storage

---

### MVP Phase 2 — Admin & LLM Settings

Goal: Allow admins to configure AI providers.

Features:

- LLM provider management
- API key encryption
- Custom base URL support
- Local model URL support
- Test connection button
- Default model selection
- Agent-wise model mapping
- Audit logs for key changes

Deliverables:

- Admin AI settings page
- Secure LLM provider storage
- LLM router service

---

### MVP Phase 3 — Agent Planning Workflow

Goal: Implement first BMAD planning workflow.

Features:

- Requirement intake UI
- BA Agent
- Architect Agent
- Data Engineer Agent
- QA Agent
- Recon Agent
- PM Agent
- Structured outputs using Pydantic models
- Agent outputs stored in PostgreSQL
- Agent workflow canvas
- Human approval step

Deliverables:

- Generate migration overview
- Generate architecture document
- Generate validation strategy
- Generate risk checklist

---

### MVP Phase 4 — Metadata & Schema Storage

Goal: Store source and target metadata.

Features:

- Manual schema upload
- CSV/JSON schema import
- Source/target connection metadata
- Table metadata storage
- Column metadata storage
- Schema snapshot history
- Basic schema comparison

Deliverables:

- Source/target metadata viewer
- Schema compare report
- Mapping draft generator

---

### MVP Phase 5 — Validation & Recon Reports

Goal: Generate useful validation and reconciliation reports.

Features:

- Row count validation
- Schema validation
- Null check definition
- Duplicate check definition
- Column-level comparison summary
- Recon report generation
- Downloadable reports

Deliverables:

- Validation center
- Recon report screen
- Exportable report artifacts

---

### MVP Phase 6 — Polish & Open-Source Launch

Goal: Prepare for public GitHub launch.

Features:

- Clean README
- CONTRIBUTING.md
- LICENSE
- SECURITY.md
- GitHub issue templates
- GitHub Actions CI
- Demo screenshots
- Demo video
- Documentation site
- Example projects

Deliverables:

- Public-ready GitHub repo
- Working Docker setup
- First community release

---

## 19. Future Roadmap

### Phase 2 Product Features

- Live database connectors
- Auto schema discovery
- Mapping generator
- Approval workflow
- Prompt versioning
- Agent memory
- Project templates
- Role-based access control

### Phase 3 Enterprise Features

- SSO
- LDAP/AD integration
- Advanced audit logs
- Secrets manager integration
- Kubernetes Helm chart
- Multi-organization isolation
- Advanced monitoring
- Deployment hardening

### Phase 4 Advanced AI Features

- AI-assisted SQL conversion
- AI mismatch explanation
- Migration simulator
- Dependency graph
- Lineage visualization
- Best-of-3 model comparison
- Local LLM support
- Sensitive-data safe mode

---

## 20. Best Practices

### Product Best Practices

- Keep BMAD as methodology, not the entire product identity
- Position as an AI migration and validation platform
- Keep MVP focused
- Build Figma design before heavy coding
- Support both business and engineering users
- Keep UI simple even when backend is complex
- Use human approval for critical AI outputs

### Engineering Best Practices

- Use modular architecture
- Keep agents, connectors, validation, and backend loosely coupled
- Store metadata, not full customer data by default
- Encrypt secrets
- Add audit logs early
- Use structured AI outputs
- Version prompts
- Add retries and workflow durability
- Make Docker installation simple

### AI Best Practices

- Do not allow random unstructured agent responses
- Use strict schemas for outputs
- Store prompts and output versions
- Track model usage per project and agent
- Add confidence score where useful
- Show why an agent made a decision
- Keep humans in the loop

### Open-Source Best Practices

- Use Apache 2.0 license for enterprise trust
- Create clear documentation
- Add good first issues
- Provide example projects
- Publish Docker images
- Keep installation simple
- Add contribution guidelines

---

## 21. License

Recommended license:

```text
Apache License 2.0
```

Apache 2.0 is enterprise-friendly and suitable for open-source infrastructure projects.

---

## 22. Final Vision

Helix Migration should become the open-source AI migration command center for enterprise data teams.

The long-term vision:

```text
Plan migrations with AI agents.
Validate data with confidence.
Reconcile source and target systems.
Track progress through enterprise dashboards.
Deploy anywhere with Docker.
```

Helix Migration is designed to be:

- Open source
- Self-hosted
- Enterprise-friendly
- AI-powered
- Validation-first
- Connector-driven
- Human-approved
- Developer-friendly
- Client-friendly

---

## 23. Current Status

```text
Status: ✅ MVP Foundation Complete (May 2026)
Backend:   49 Python files, 10 API routers, 58 passing tests
Frontend:  23 TSX/TS files, 15 pages wired to API
Agents:    13 BMAD agents, LangGraph StateGraph, PydanticAI runtime
Worker:    Temporal workflow/activity/worker skeleton
Database:  7 Alembic migrations, PostgreSQL metadata store
Docker:    7 services via docker-compose.dev.yml
```

**What's implemented:**
- ✅ Repository structure and Docker Compose setup
- ✅ Backend API with full CRUD (projects, LLM providers, artifacts, workflows)
- ✅ Authentication with JWT, bcrypt, RBAC, and organization isolation
- ✅ LLM provider management (OpenAI, Claude, Gemini, DeepSeek, OpenRouter, Custom, Local)
- ✅ BMAD + LangGraph agent planning workflow (BA → Architect → VP → Approval)
- ✅ PydanticAI-compatible structured output runtime (JSON extraction, validation)
- ✅ Temporal workflow/activity/worker skeleton
- ✅ Workflow persistence in PostgreSQL
- ✅ Frontend premium app shell with 15 wired pages
- ✅ Developer workspace with artifact upload and AI code review
- ✅ Validation center and reconciliation dashboard
- ✅ Audit logs and system health monitoring
- ✅ Safe artifact upload with path traversal protection
- ✅ API key encryption and masking

**Quick start:** See [Installation](#17-installation) section.

---

## 24. Contributing

Contributions are welcome! The MVP foundation is complete.

**Areas to contribute:**

- Frontend UI components and pages
- Backend API endpoints
- BMAD agent workflows and nodes
- Database connectors
- Validation and reconciliation rules
- Documentation and tutorials
- Docker and deployment improvements
- Example migration templates

See `CONTRIBUTING.md` and `CODE_REVIEW.md` for project architecture and code mapping.

---

## 25. Maintainer

Created by Datainteg.

```text
Website: https://helix.datainteg.io
GitHub: https://github.com/datainteg/helix-ai-migration
```

Actual documentation structure:

```text
docs/
  agents/
  backend/
  connectors/
  deployment/
  developer-workspace/
  frontend/
  governance/
  import-export/
  knowledge/
  mvp/
  notifications/
  observability/
  operations/
  plugins/
  project-planning/
  security/
  storage/
  templates/
  validation/
```

Root-level documents provide high-level contracts. `docs/` subfolders provide deeper implementation and operations guidance.

---

## 26. Developer Execution Layer

Helix Migration has two product layers:

| Layer | Purpose |
|---|---|
| Management Layer | Dashboard, projects, subprojects, agents, validation, reconciliation, reports, approvals, admin panel, and LLM settings |
| Developer Execution Layer | Code Review Center, ETL Migration Workspace, DAG/workflow analysis, code analysis, draft code migration, notebook generation, side-by-side diffs, artifact versioning, and human approval for generated code |

The Developer Execution Layer extends Helix Migration beyond migration management dashboards. It gives engineers a workspace to upload existing migration and ETL code, analyze it with AI agents, generate draft target artifacts, compare original and generated code, and approve versioned outputs.

Important scope statement:

```text
Helix Migration generates draft migration code, notebook structures, validation plans, and reconciliation reports that must be reviewed and approved by humans before production use.
```

### Developer Workspace

The Developer Workspace is a developer-focused workspace where engineers can upload existing migration and ETL code, review it with AI agents, convert it into target draft formats, generate notebooks, review diffs, and store versioned artifacts.

### Code Review Center

The Code Review Center should support:

- Upload `.py`, `.sql`, `.ipynb`, DAG files, and config files
- AI code analysis
- AI code review
- Formatting suggestions
- Security and quality checks
- Dependency extraction
- Transformation logic extraction
- Side-by-side original vs generated code diff
- Review comments
- Approval or rejection workflow
- Export generated draft code

### ETL Migration Workspace

The ETL Migration Workspace should support:

- Legacy job inventory
- ETL code analyzer
- DAG/workflow analyzer
- Dependency graph
- Transformation logic extractor
- Code conversion
- Databricks notebook generator
- Validation mapping
- Migration readiness score

### Developer-Focused Agents

| Agent | Responsibilities |
|---|---|
| Code Analyzer Agent | Read uploaded code; extract inputs, outputs, dependencies, transformations, joins, filters, aggregations; identify risks and complexity |
| Code Review Agent | Review code quality, anti-patterns, formatting improvements, security risks, hardcoded secrets, and performance issues |
| Code Migration Agent | Generate target code drafts, convert legacy logic into modern code patterns, preserve business logic, and explain assumptions and limitations |
| Notebook Generator Agent | Convert supported scripts into Databricks notebook-style structure with markdown explanation cells, code cells, validation cells, and execution notes |
| DAG / Workflow Review Agent | Review DAG and workflow dependencies, detect cycles and duplicate task IDs, review retries, timeouts, sensors, scheduling, owners, and generate a workflow quality report |
| Version Control Agent | Track source artifact versions, generated artifact versions, change summaries, and links to agent outputs and approvals |

### Code Conversion Use Cases

- Python `.py` script to Databricks notebook draft
- SQL job to optimized SQL / dbt-style model draft
- SAS logic to Databricks notebook draft
- Legacy ETL script to PySpark draft
- Existing Airflow DAG review
- DAG dependency and cycle validation
- Workflow scheduling, retry, and timeout review

### Version-Controlled Artifacts

Uploaded and generated artifacts should be tracked as versioned records. PostgreSQL stores artifact metadata, content hashes, review status, lineage, approvals, and links to agent outputs. Actual uploaded/generated files should be stored on the local filesystem for MVP and in MinIO/S3-compatible storage later, while PostgreSQL remains the metadata source of truth.

### Developer Execution Architecture

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

### MVP Scope Note

Developer Execution MVP should include upload for `.py` and `.sql` files, artifact metadata, code analysis, AI explanation, code review summary, draft converted code or Databricks notebook structure, side-by-side diff, saved artifact versions, and human approval status.

---

## 27. Final Layered Architecture

Helix Migration is designed as a complete enterprise-grade, open-source, self-hosted AI migration and validation platform. The platform has 19 architecture layers, but MVP implementation must remain focused.

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

MVP should include the dashboard, admin and LLM settings, project workspace, BMAD agent workflow, PostgreSQL metadata store, basic developer workspace, basic artifact versioning, basic validation/recon report, Docker Compose setup, lightweight audit logs, basic system health page, static JSON/YAML templates, and safe code analysis only.

MVP should not include a full marketplace, full vector memory, full Git integration, full production execution engine, all connectors, full Kubernetes support, automatic deployment of generated code, arbitrary code execution, or full notebook execution runtime.

Use this product rule throughout the project:

```text
Helix Migration generates draft migration code, notebook structures, validation plans, and reconciliation reports that must be reviewed and approved by humans before production use.
```

### Governance & Audit

Governance and audit capabilities should include user activity logs, agent decision logs, approval history, prompt/version history, LLM usage logs, data access logs, generated artifact history, and exportable audit reports.

### Observability

Observability should include system health, worker health, Temporal workflow status, agent execution logs, failed jobs, token usage, LLM latency, API latency, connector status, and validation job runtime.

### Templates

MVP templates should be static JSON/YAML files. Planned templates include Oracle to Snowflake, SQL Server to Databricks, SAS to Databricks, Python ETL to Databricks Notebook, SQL Jobs to dbt Models, Airflow DAG Review, DataStage Migration Planning, and Generic Source to Target Validation.

### Plugin / Extension Layer

The plugin layer should eventually support custom connectors, custom validation rules, custom agents, custom templates, custom report formats, and custom LLM providers. Plugin execution must respect security and tenant boundaries.

### Artifact Storage

PostgreSQL stores artifact metadata only: path, content hash, version, owner, approval status, storage provider, metadata, and audit trail. Uploaded/generated files should be stored in local filesystem storage for MVP and MinIO/S3-compatible storage later.

Artifact examples include uploaded `.py`, `.sql`, and `.ipynb` files, generated notebooks, generated code files, recon reports, validation exports, mapping files, and documentation exports.

### Secrets Management

MVP should store encrypted API keys and secrets through backend-managed encryption, return only masked values, and support key rotation. Future enterprise support should include Docker secrets, HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, and GCP Secret Manager.

### Notifications

Notifications are planned for future phases: email, Slack, Teams webhooks, approval reminders, validation failure alerts, and agent completion alerts. Admin-side SMTP configuration should support host, port, username, encrypted password or secret reference, from email, TLS/STARTTLS options, enabled status, and test email.

### Import / Export

Import/export should support PDF, Markdown, JSON, CSV, HTML, project config export, migration plan export, validation report export, recon report export, agent outputs export, and templates export.

### Safe Execution

Uploaded code is untrusted input. MVP must not execute arbitrary uploaded code. MVP behavior is analysis, review, draft conversion, notebook structure generation, diff review, and human approval. Future execution, if added, must use sandboxing, isolated containers, resource limits, and strict security boundaries.
