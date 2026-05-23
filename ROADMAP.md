# Roadmap

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

## ✅ MVP Foundation — COMPLETE (May 2026)

All 21 prompts implemented. See `CODE_REVIEW.md` for full audit.

**Implemented:**
- ✅ Repository structure + Docker Compose (7 services)
- ✅ Frontend premium app shell (15 pages, 23 TSX/TS files)
- ✅ Backend API (10 routers, 49 Python files, 58 tests)
- ✅ PostgreSQL metadata store (8 models, 7 migrations)
- ✅ Authentication (JWT, bcrypt, RBAC, org isolation)
- ✅ LLM provider management (7 provider types)
- ✅ BMAD + LangGraph agent workflow (4-node graph, 13 agents registered)
- ✅ PydanticAI structured output runtime (JSON extraction, validation)
- ✅ Temporal workflow/activity/worker skeleton
- ✅ Developer workspace + AI code review
- ✅ Validation center + reconciliation dashboard
- ✅ Audit logs + system health
- ✅ Safe artifact upload with security controls
- ✅ API key encryption and masking

## 🟡 Phase 2 — Agent Expansion (In Progress)

**Goal:** Wire all 13 BMAD agents into the LangGraph.

| Feature | Status |
|---|---|
| BA Agent (Mary) | ✅ Wired |
| Architect Agent (Winston) | ✅ Wired |
| Data Engineer (Amelia) | 🔜 Ready |
| QA/Validation Agent | 🔜 Ready |
| Recon Agent | 🔜 Ready |
| DevOps Agent | 🔜 Ready |
| PM Agent (John) | 🔜 Ready |
| Party Mode orchestrator | 🔜 Ready |
| Real LLM provider calls | 🔜 Router ready |

## 🔜 Phase 3 — Live Connectors

| Feature | Status |
|---|---|
| PostgreSQL connector | 🔜 Planned |
| MySQL connector | 🔜 Planned |
| Oracle connector | 🔜 Planned |
| Snowflake connector | 🔜 Planned |
| Schema discovery | 🔜 Planned |
| CSV/JSON import | 🔜 Planned |

## 🔜 Phase 4 — Enterprise Features

| Feature | Status |
|---|---|
| SSO / OAuth | 🔜 Planned |
| Kubernetes Helm chart | 🔜 Planned |
| Advanced RBAC | 🔜 Planned |
| Prometheus metrics | 🔜 Planned |
| Multi-tenant isolation | 🔜 Planned |
| Rate limiting | 🔜 Planned (see IMPROVEMENTS.md) |

## 🔜 Phase 5 — Advanced AI

| Feature | Status |
|---|---|
| AI-assisted SQL conversion | 🔜 Planned |
| Code migration agent | 🔜 Planned |
| Notebook generator | 🔜 Planned |
| DAG/workflow analyzer | 🔜 Planned |
| Best-of-3 model comparison | 🔜 Planned |
| Local LLM support (Ollama/LM Studio) | 🔜 Planned |

---

**See `IMPROVEMENTS.md` for detailed code quality, performance, security, and workflow recommendations.**
**See `CODE_REVIEW.md` for complete file-to-prompt mapping and audit.**

Goal: Support bring-your-own-key model configuration.

Planned:

- OpenAI / ChatGPT
- Google Gemini
- Anthropic Claude
- DeepSeek
- OpenRouter
- Custom OpenAI-compatible API
- Local model URL
- Key encryption
- Key masking
- Key rotation
- Agent-wise model mapping

## Agent Workflow Phase

Goal: Implement the first BMAD migration planning workflow.

Planned:

- Requirement intake
- Business Analyst Agent
- Architect Agent
- Human approval
- Data Engineer Agent
- QA / Validation Agent
- Recon Agent
- DevOps Agent
- PM Agent
- Final review and sign-off
- Typed outputs with PydanticAI
- Durable orchestration with Temporal

## Metadata Phase

Goal: Store source and target metadata in PostgreSQL.

Planned:

- Source system metadata
- Target system metadata
- Schema storage
- Table storage
- Column storage
- Schema snapshots
- Basic schema comparison

## Validation and Recon Phase

Goal: Provide practical migration quality checks.

Planned:

- Schema validation
- Row count checks
- Null checks
- Duplicate checks
- Distribution checks
- Checksum strategy
- Reconciliation summaries
- Downloadable reports
- AI mismatch explanations

## Developer Execution Phase

Goal: Add engineering execution support for migration code and ETL artifacts.

Planned:

- Developer Workspace
- Code Review Center
- ETL Migration Workspace
- Artifact upload for `.py`, `.sql`, `.ipynb`, DAG files, and config files
- Code Analyzer Agent
- Code Review Agent
- Code Migration Agent
- Notebook Generator Agent
- DAG / Workflow Review Agent
- Version Control Agent
- Side-by-side diff viewer
- Artifact versioning
- Human approval workflow for generated code
- Validation and reconciliation plan linkage

## Connector Phase

Goal: Add connector framework and first connector implementations.

Planned:

- Connector interface
- Test connection
- Schema scan
- Metadata extraction
- PostgreSQL connector
- MySQL connector
- SQL Server connector
- Oracle connector
- Snowflake connector
- File connector
- Databricks connector

## Enterprise Phase

Goal: Harden for larger enterprise deployments.

Planned:

- SSO
- LDAP/AD integration
- Advanced RBAC
- Secrets manager integration
- Helm chart
- Advanced audit search
- Monitoring and alerting
- Multi-organization hardening
- Policy controls

## Future AI Features

Planned:

- AI-assisted SQL conversion
- Draft code and notebook generation with required human approval
- DAG/workflow analysis and readiness scoring
- AI-generated mapping drafts
- AI mismatch explanation
- Best-of-3 model comparison
- Migration simulator
- Dependency graph
- Lineage visualization
- Local LLM support with Ollama, vLLM, and LM Studio
- Sensitive-data safe mode

## Final Phased Roadmap

### Phase 1: Core Platform

- Core platform
- Admin panel
- LLM settings
- Project workspace
- BMAD agents
- PostgreSQL metadata
- Docker Compose

### Phase 2: Developer Workspace

- Developer Workspace
- Code Review Center
- Artifact versioning
- Basic code analysis
- Basic notebook generation
- Side-by-side diff

### Phase 3: Validation & Recon

- Schema compare
- Row count
- Recon reports
- Validation templates

### Phase 4: Governance & Observability

- Audit logs
- System health
- Token usage
- Worker monitoring

### Phase 5: Templates & Plugins

- Migration templates
- Connector plugins
- Validation plugins
- Report templates

### Phase 6: Enterprise Hardening

- Secrets manager integrations
- SSO
- Advanced RBAC
- Helm chart
- MinIO/S3 storage

### Phase 7: Advanced AI

- AI mismatch explanation
- Migration simulator
- Knowledge memory
- Local LLM support
- Safe sandboxed execution, if required
