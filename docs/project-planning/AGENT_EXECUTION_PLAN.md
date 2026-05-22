# Agent Execution Plan

## Runtime Stack

| Component | Role |
|---|---|
| BMAD | Migration planning methodology |
| LangGraph | Agent orchestration |
| PydanticAI | Structured output validation |
| Temporal OSS | Durable workflows and retries |
| LLM Router | Provider/model routing |
| PostgreSQL | Tasks, outputs, prompts, approvals, audit metadata |

## BMAD Workflow

```text
Requirement
  -> Business Analyst Agent
  -> Architect Agent
  -> Human Approval
  -> Data Engineer Agent
  -> QA / Validation Agent
  -> Recon Agent
  -> DevOps Agent
  -> PM Agent
  -> Final Review
```

## LangGraph Orchestration

- Represent each agent as a node.
- Represent approvals and failure handling as explicit graph transitions.
- Store graph state in durable workflow state and PostgreSQL-visible records.
- Keep side effects idempotent where retries are possible.

## PydanticAI Output Schemas

Every agent output must be:

- Typed
- Validated
- Stored
- Auditable
- Versioned where needed

Common fields:

- `summary`
- `assumptions`
- `risks`
- `open_questions`
- `recommendations`
- `confidence_score`
- `source_references`
- `prompt_version`
- `llm_provider_id`
- `llm_model`

## LLM Router

The router should support:

- Default model mode
- Agent-wise model mapping
- Provider fallbacks where configured
- Timeout and retry settings
- Token and latency logging
- Custom OpenAI-compatible API
- Local model URL

## Agent Output Storage

Store in PostgreSQL:

- Agent task metadata
- Input payload references
- Typed output payloads
- Prompt version
- Model/provider metadata
- Workflow state
- Approval state
- Audit records

Do not store full production business data by default.

## Approval Workflow

Human approval is required for:

- Architecture plan progression
- Generated draft code or notebook artifacts
- Final migration and validation reports before production use

Approval states:

- Pending
- Approved
- Rejected
- Changes requested
- Cancelled

## Safe Execution Rules

- Developer agents generate reviews and draft artifacts only.
- MVP must not execute arbitrary uploaded code.
- Uploaded code is untrusted input.
- Future execution, if required, must use sandboxing, isolated containers, resource limits, and strict security boundaries.

## First Agents to Implement

| Agent | MVP purpose |
|---|---|
| Business Analyst Agent | Create migration brief from requirement |
| Architect Agent | Create architecture plan and approval artifact |
| QA / Validation Agent | Draft validation plan |
| Recon Agent | Draft reconciliation plan |
| Code Analyzer Agent | Extract inputs, outputs, dependencies, transformations, and risks |
| Code Review Agent | Identify quality, security, performance, and maintainability findings |

## Future Agents

- Data Engineer Agent
- DevOps Agent
- PM Agent
- Code Migration Agent
- Notebook Generator Agent
- DAG / Workflow Review Agent
- Version Control Agent
- Compliance Review Agent
- Failure Analysis Agent
- Template Recommendation Agent

## Related Architecture Docs

| Doc | What it covers |
|---|---|
| `AGENT_WORKFLOW.md` | Core BMAD flow, roles, memory, retries, approvals |
| `docs/agents/AGENT_RUNTIME_GUIDE.md` | LangGraph structure, PydanticAI schemas, prompt registry, agent lifecycle |
| `docs/agents/LLM_ROUTER.md` | Provider abstraction, routing modes, fallback, usage logging |
| `docs/agents/PROMPT_ENGINEERING.md` | Prompt templates, versioning, evaluation methodology |
| `docs/security/SAFE_EXECUTION.md` | Safe execution rules for developer agents |
