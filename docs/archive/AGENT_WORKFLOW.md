# Agent Workflow

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

Helix Migration uses AI agents to help teams plan, validate, reconcile, and manage enterprise migrations. The platform must keep humans in control and store every important output as typed, reviewable metadata.

> **Reality note (2026-05-23):** Today the 4 wired BMAD nodes (`business_analyst`, `architect`, `validation_planner`, `approval_gate` in [agents/bmad/nodes.py](agents/bmad/nodes.py)) construct their `BusinessAnalystOutput` / `ArchitectOutput` / `ValidationPlanOutput` outputs with **hardcoded strings** — they do not call any LLM. The infrastructure to do so (`agents.runtime.llm_router.route_llm_call()`, `agents.runtime.structured_output.build_mock_agent_response()`) exists but is not invoked from the nodes. The other 9 of 13 registered BMAD agents are metadata-only references. Tracked as C-7 in [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md).

## Methodology and Runtime

| Layer | Technology | Purpose |
|---|---|---|
| Methodology | BMAD | Migration planning lifecycle and agent responsibilities |
| Orchestration | LangGraph | Agent graph, state transitions, and branching |
| Structured output | PydanticAI | Typed model outputs and validation |
| Durability | Temporal OSS | Long-running workflows, retries, signals, and recovery |
| Persistence | PostgreSQL | Tasks, outputs, prompts, approvals, reports, and audit logs |
| Model routing | LLM Router | Provider selection and agent-wise model mapping |

BMAD provides the default workflow, but Helix Migration should remain a platform that can support other workflow templates later.

## Core Flow

```text
User Requirement
  -> Business Analyst Agent
  -> Architect Agent
  -> Human Approval
  -> Data Engineer Agent
  -> QA / Validation Agent
  -> Recon Agent
  -> DevOps Agent
  -> PM Agent
  -> Final Review & Sign-off
```

## Agent Roles

| Agent | Responsibility | Primary output |
|---|---|---|
| Business Analyst Agent | Understand requirements, scope, assumptions, risks | Migration brief |
| Architect Agent | Create target architecture, system flow, dependencies | Architecture plan |
| Data Engineer Agent | Define mapping, transformation, loading approach | Engineering plan |
| QA / Validation Agent | Create validation strategy and rule candidates | Validation plan |
| Recon Agent | Define reconciliation checks and report strategy | Recon plan |
| DevOps Agent | Plan deployment, cutover, rollback, observability | Cutover plan |
| PM Agent | Track status, risks, owners, timeline, approvals | Project control summary |

## Agent Communication

Each agent receives:

- Project metadata
- Requirement version
- Relevant previous agent outputs
- Human decisions
- Prompt version
- Model configuration
- Allowed tools and constraints

Each agent returns:

- Typed output payload
- Assumptions
- Risks
- Questions
- Confidence score when useful
- Evidence references
- Recommended next step

## Human Approval

Human approval is required after the Architect Agent before execution-oriented agents continue.

Approval records should include:

- Approver
- Approved artifact
- Artifact version
- Decision
- Notes
- Timestamp

Workflow should support approve, reject, request changes, and cancel.

## Memory Management

Agent memory should be scoped:

| Memory type | Scope | Example |
|---|---|---|
| Short-term | Workflow run | Current decisions and intermediate outputs |
| Project memory | Project | Architecture choices, assumptions, source/target context |
| Organization memory | Organization | Approved provider settings, reusable standards |

Memory must not include full customer business data by default.

## Prompt Versioning

Prompt templates and versions should be stored in PostgreSQL.

Track:

- Template name
- Agent type
- Version
- Author
- Status
- Created timestamp
- Change notes

Agent tasks should reference the exact prompt version used.

## Failure Handling

Failures should be explicit and recoverable.

| Failure | Handling |
|---|---|
| LLM provider timeout | Retry with backoff, then mark task failed |
| Invalid structured output | Retry with schema repair instruction |
| Missing metadata | Pause workflow and request user input |
| Human rejection | Return to responsible agent with feedback |
| Temporal activity failure | Retry according to workflow policy |
| Provider unavailable | Use configured fallback if allowed |

## Retry Strategy

- Use Temporal retries for durable activities.
- Use bounded retries for LLM calls.
- Do not retry unsafe side effects without idempotency keys.
- Store attempt count and failure reason.
- Surface retry status in the workflow UI.

## Structured Output Example

Agent outputs must use typed schemas. Example shape:

```json
{
  "summary": "Migration scope and business objective",
  "assumptions": ["Source schema is stable during assessment"],
  "risks": [
    {
      "title": "Missing target data quality rules",
      "severity": "medium",
      "mitigation": "Create validation rules before cutover"
    }
  ],
  "open_questions": ["What is the cutover window?"],
  "recommended_next_step": "Review architecture plan",
  "confidence_score": 0.82
}
```

The exact schema should be defined in code during implementation and versioned in documentation.

## Workflow State

Workflow state should include:

- Pending
- Running
- Waiting for approval
- Waiting for input
- Failed
- Cancelled
- Completed

State changes should be audit logged.

## Developer Agent Workflow

The Developer Execution Layer uses specialized agents for uploaded code, ETL jobs, notebooks, DAGs, and generated draft artifacts.

```text
Upload Code
  -> Code Analyzer Agent
  -> Code Review Agent
  -> Code Migration Agent
  -> Notebook Generator Agent, if required
  -> Side-by-side Diff Review
  -> Human Approval
  -> Version Control Agent
  -> Store Artifact Metadata
  -> Link to Validation / Recon Plan
```

Helix Migration generates draft migration code, notebook structures, validation plans, and reconciliation reports that must be reviewed and approved by humans before production use.

## Developer Agent Roles

| Agent | Responsibilities |
|---|---|
| Code Analyzer Agent | Read uploaded code; extract inputs, outputs, dependencies, transformations, joins, filters, aggregations; identify risks and complexity |
| Code Review Agent | Review quality, anti-patterns, formatting, hardcoded secrets, security risks, and performance issues |
| Code Migration Agent | Generate target code draft, convert legacy logic into modern code patterns, preserve business logic, and explain assumptions and limitations |
| Notebook Generator Agent | Convert supported scripts into Databricks notebook-style structure with markdown explanation cells, code cells, validation cells, and execution notes |
| DAG / Workflow Review Agent | Review dependencies, cycles, duplicate task IDs, retries, timeouts, sensors, scheduling, owners, and workflow quality |
| Version Control Agent | Track source versions, generated versions, change summaries, links to agent outputs, and approvals |

## Code Review Flow

```text
Upload artifact
  -> Extract metadata and content hash
  -> Analyze dependencies and transformation logic
  -> Review quality, security, performance, and maintainability
  -> Create review summary and comments
  -> Show AI Review Panel and side-by-side diff when generated output exists
  -> Approve, reject, or request changes
```

## Notebook Generation Flow

```text
Supported script
  -> Code Analyzer Agent
  -> Code Migration Agent
  -> Notebook Generator Agent
  -> Markdown explanation cells
  -> Code cells
  -> Validation cells
  -> Execution notes
  -> Human review and approval
```

## Artifact Approval Flow

Generated code remains draft until a human approves it. Approval records should include artifact version, approver, decision, notes, timestamp, and links to review or conversion runs.

## Version Control Lifecycle

```text
uploaded
  -> analyzed
  -> reviewed
  -> converted
  -> generated
  -> diff_reviewed
  -> approved_or_rejected
  -> linked_to_validation
```

The Version Control Agent should maintain source artifact versions, generated artifact versions, content hashes, change summaries, lineage, and approval status.

## Final Agent Families

| Family | Agents |
|---|---|
| Migration Planning Agents | Business Analyst Agent, Architect Agent, Data Engineer Agent, QA/Validation Agent, Recon Agent, DevOps Agent, PM Agent |
| Developer Execution Agents | Code Analyzer Agent, Code Review Agent, Code Migration Agent, Notebook Generator Agent, DAG / Workflow Review Agent, Version Control Agent |
| Governance Agents, future | Compliance Review Agent, Audit Summary Agent |
| Observability Agents, future | Failure Analysis Agent, Cost/Token Optimization Agent |
| Template Agents, future | Template Recommendation Agent |

Every agent output must be typed, validated, stored, versioned where needed, and auditable. Agent outputs should include assumptions, limitations, confidence where useful, prompt version, model/provider metadata, and links to source artifacts or project metadata.

Developer agents generate reviews and draft code only. They do not execute uploaded code in MVP. Helix Migration generates draft migration code, notebook structures, validation plans, and reconciliation reports that must be reviewed and approved by humans before production use.

## Terminology

- BMAD means Business, Mission, Architecture, Design migration methodology.
- Pydantic validates backend and API data structures.
- PydanticAI validates structured LLM outputs.
- Temporal OSS is the durable workflow engine; use "Temporal" after first mention.

## Related Docs

| Doc | What it covers |
|---|---|
| `docs/agents/AGENT_RUNTIME_GUIDE.md` | Runtime stack, BMAD templates, LangGraph structure, PydanticAI schemas, LLM router, prompt registry, agent lifecycle |
| `docs/agents/LLM_ROUTER.md` | Provider abstraction, routing modes, fallback, retries, usage logging |
| `docs/agents/PROMPT_ENGINEERING.md` | Prompt template design, versioning, evaluation, few-shot examples |
| `docs/mvp/CODEX_TASKS.md` | Task-level agent implementation with prompt mappings |
| `docs/project-planning/AGENT_EXECUTION_PLAN.md` | Agent runtime build plan, first agents, approval workflow |
| `docs/security/SAFE_EXECUTION.md` | Safe execution rules for developer agents |
| `docs/developer-workspace/DEVELOPER_WORKSPACE.md` | Developer agent workspace integration |
