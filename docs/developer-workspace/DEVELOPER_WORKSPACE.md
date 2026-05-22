# Developer Workspace

## Purpose

The Developer Workspace is the Developer Execution Layer for Helix Migration. It gives engineers a place to upload existing migration and ETL artifacts, analyze them with AI agents, review quality and risks, generate draft target artifacts, compare diffs, and approve versioned outputs.

Helix Migration generates draft migration code, notebook structures, validation plans, and reconciliation reports that must be reviewed and approved by humans before production use.

## Product Layers

| Layer | Product areas |
|---|---|
| Management Layer | Dashboard, projects, subprojects, agents, validation, reconciliation, reports, approvals, admin panel, LLM settings |
| Developer Execution Layer | Developer Workspace, Code Review Center, ETL Migration Workspace, DAG / Workflow Analyzer, artifact versioning, generated-code approvals |

## Supported Artifact Types

MVP:

- `.py`
- `.sql`

Planned:

- `.ipynb`
- Airflow DAG files
- Workflow config files
- SAS scripts
- Shell scripts
- dbt models
- ETL tool exports

## Agent Flow

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

## UI Layout

| Area | Content |
|---|---|
| Left panel | Project files, uploaded artifacts, versions |
| Center panel | Source code, generated code, notebook preview, diff view |
| Right panel | AI analysis, suggestions, risks, assumptions, approval actions |
| Bottom panel | Logs, validation output, generated files, version history |

## Artifact Versioning

Artifact versioning should track:

- Source artifact
- Generated artifact
- Version number
- Source content hash
- Generated content hash
- Change summary
- Agent that generated output
- LLM provider and model
- Approval status
- Links to reviews, conversions, validation plans, and recon plans

PostgreSQL stores artifact metadata and hashes. Actual uploaded files should be stored on the local filesystem for MVP and in MinIO/S3-compatible storage later.

## Approval Lifecycle

```text
draft
  -> under_review
  -> approved
```

Alternative states:

```text
rejected
changes_requested
superseded
```

Generated artifacts must not be treated as production-ready before approval.

## MVP Scope

Included:

- Upload `.py` and `.sql` files
- Store artifact metadata
- Analyze uploaded code
- Generate AI explanation
- Generate code review summary
- Generate draft converted code or Databricks notebook structure
- Show side-by-side diff
- Save versioned artifact
- Track human approval status

Excluded:

- Full automated production migration
- Complex multi-file project conversion
- Automatic deployment of generated code
- Full Git integration
- Full notebook execution runtime
- All ETL tools support
- Arbitrary uploaded-code execution
- Automatic production deployment of generated code

## Future Roadmap

- Multi-file project import
- Git provider integration
- Object storage for artifact content
- Notebook execution integration
- Advanced dependency graph
- ETL tool export parsers
- SAS-to-Databricks conversion assistant
- dbt model draft generation
- Workflow readiness scoring
- Generated artifact promotion workflow

## Related Docs

| Doc | What it covers |
|---|---|
| `CODE_REVIEW_CENTER.md` | Upload, AI analysis, review comments, diff viewer, approval workflow |
| `ETL_MIGRATION_WORKSPACE.md` | ETL flow, DAG analysis, transformation extraction, notebook generation, readiness scoring |
| `../../AGENT_WORKFLOW.md` | Developer agent roles and execution flow |
| `../../API_DESIGN.md` | Artifact, code review, conversion, and approval API routes |
| `../storage/ARTIFACT_STORAGE.md` | Artifact metadata vs file storage separation |
| `../security/SAFE_EXECUTION.md` | Safe execution rules for uploaded code |
- Object storage for artifact content
- Notebook execution integration
- Advanced dependency graph
- ETL tool export parsers
- SAS-to-Databricks conversion assistant
- dbt model draft generation
- Workflow readiness scoring
- Generated artifact promotion workflow
