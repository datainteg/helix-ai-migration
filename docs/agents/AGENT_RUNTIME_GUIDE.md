# Agent Runtime Guide

Helix Migration agent runtime combines BMAD methodology, LangGraph orchestration, PydanticAI structured outputs, Temporal durability, PostgreSQL persistence, and an LLM router.

## Runtime Goals

- Produce structured migration planning artifacts.
- Keep humans in the loop.
- Store all important outputs in PostgreSQL.
- Make retries and failures visible.
- Support multiple LLM providers.
- Avoid unstructured random agent output.

## BMAD Workflow Templates

Default workflow:

```text
Requirement Intake
  -> Business Analysis
  -> Architecture Planning
  -> Human Approval
  -> Data Engineering Plan
  -> QA / Validation Plan
  -> Reconciliation Plan
  -> DevOps Cutover Plan
  -> PM Summary
  -> Final Review
```

Each template should define:

- Steps
- Agent role
- Required input
- Output schema
- Approval gates
- Retry policy
- Completion criteria

## LangGraph Structure

Recommended graph nodes:

- `intake`
- `business_analyst`
- `architect`
- `approval_gate`
- `data_engineer`
- `qa_validation`
- `recon`
- `devops`
- `pm`
- `final_review`

Edges should represent normal flow, rejection flow, retry flow, and failure flow.

## PydanticAI Output Schemas

Every agent output should be typed.

Common fields:

- `summary`
- `assumptions`
- `risks`
- `open_questions`
- `recommendations`
- `artifacts`
- `confidence_score`

Example:

```json
{
  "summary": "Target migration approach",
  "assumptions": ["Target warehouse is available before validation"],
  "risks": [
    {
      "title": "Schema drift",
      "severity": "high",
      "mitigation": "Capture schema snapshots before each validation run"
    }
  ],
  "open_questions": [],
  "recommendations": ["Approve architecture before mapping work"],
  "confidence_score": 0.86
}
```

## LLM Router

The LLM router should support:

- OpenAI / ChatGPT
- Google Gemini
- Anthropic Claude
- DeepSeek
- OpenRouter
- Custom OpenAI-compatible API
- Local model URL
- Future Ollama, vLLM, and LM Studio

Routing modes:

- Default model for all agents
- Agent-wise model mapping

## Provider Abstraction

Provider abstraction should normalize:

- Chat messages
- System prompts
- Structured output request
- Timeout
- Retryable errors
- Token usage
- Model name
- Provider response metadata

## Agent Memory

Memory should be scoped:

- Workflow memory
- Project memory
- Organization standards

Memory should not contain full production business data by default.

## Prompt Registry

Prompt registry should track:

- Template name
- Agent type
- Version
- Status
- Content
- Author
- Created timestamp
- Change notes

Agent tasks must store the prompt version used.

## Agent Task Lifecycle

```text
created
  -> queued
  -> running
  -> validating_output
  -> waiting_for_approval
  -> completed
```

Failure states:

```text
failed
cancelled
timed_out
requires_input
```

## PostgreSQL Storage

Store:

- Agent definitions
- Agent tasks
- Agent outputs
- Prompt templates
- Prompt versions
- Agent memory
- Workflow runs
- Workflow steps
- Approvals
- Failures
- Audit logs

## Retries and Approvals

- Retry LLM calls with bounded backoff.
- Retry Temporal activities according to policy.
- Store every failed attempt.
- Require approval after architecture planning.
- Allow request changes to route back to the responsible agent.
- Audit approval decisions.

## Developer Execution Agents

Developer agents support uploaded code, ETL migration review, notebook generation, DAG review, and versioned artifacts. Helix Migration generates draft migration code, notebook structures, validation plans, and reconciliation reports that must be reviewed and approved by humans before production use.

### Code Analyzer Agent

Responsibilities:

- Read uploaded code.
- Extract inputs, outputs, dependencies, transformations, joins, filters, and aggregations.
- Identify risks and complexity.

Structured output fields:

- `artifact_summary`
- `inputs`
- `outputs`
- `dependencies`
- `transformations`
- `joins`
- `filters`
- `aggregations`
- `complexity_score`
- `risks`

### Code Review Agent

Responsibilities:

- Review code quality.
- Identify anti-patterns.
- Suggest formatting improvements.
- Detect security risks.
- Detect hardcoded secrets.
- Detect performance issues.

Structured output fields:

- `quality_score`
- `risk_score`
- `security_findings`
- `performance_findings`
- `formatting_suggestions`
- `review_comments`
- `recommended_actions`

### Code Migration Agent

Responsibilities:

- Generate target code draft.
- Convert legacy logic into modern code patterns.
- Preserve business logic.
- Explain assumptions and limitations.

Structured output fields:

- `target_type`
- `generated_artifact_ref`
- `business_logic_preserved`
- `assumptions`
- `limitations`
- `manual_review_required`

### Notebook Generator Agent

Responsibilities:

- Convert supported scripts into Databricks notebook-style structure.
- Add markdown explanation cells.
- Add code cells.
- Add validation cells.
- Add execution notes.

Structured output fields:

- `notebook_title`
- `cells`
- `validation_cells`
- `execution_notes`
- `assumptions`
- `manual_review_required`

### DAG / Workflow Review Agent

Responsibilities:

- Review DAG and workflow dependencies.
- Detect cycles.
- Detect duplicate task IDs.
- Review retries, timeouts, sensors, scheduling, and owners.
- Generate workflow quality report.

Structured output fields:

- `duplicate_task_ids`
- `cycles_detected`
- `missing_timeouts`
- `risky_sensors`
- `schedule_findings`
- `owner_findings`
- `quality_score`
- `report`

### Version Control Agent

Responsibilities:

- Track source artifact versions.
- Track generated artifact versions.
- Maintain change summaries.
- Link artifacts to agent outputs and approvals.

Structured output fields:

- `source_artifact_version_id`
- `generated_artifact_version_id`
- `change_summary`
- `lineage_links`
- `approval_status`

## Final Agent Runtime Requirements

Agent families:

- Migration Planning Agents
- Developer Execution Agents
- Governance Agents, future
- Observability Agents, future
- Template Recommendation Agents, future

Every agent output must be typed, validated, stored, auditable, and versioned where needed. Store prompt version, LLM provider, model, token usage, latency, assumptions, limitations, confidence where useful, and source artifact references.

Agent memory:

- Project memory for decisions and context
- Organization memory for standards and approved patterns
- Reusable validation rules
- Approved migration/code patterns

Safe execution:

- Developer agents do not execute uploaded code in MVP.
- Uploaded code is untrusted input.
- Code agents analyze, review, and generate draft artifacts only.
- Future execution must use sandboxed containers, strict resource limits, and access boundaries.
