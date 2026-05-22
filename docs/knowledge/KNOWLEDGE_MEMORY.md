# Knowledge and Memory

## Purpose

The Knowledge & Memory Layer stores reusable migration context, approved patterns, organization standards, and project decisions. It improves continuity without storing full customer production data by default.

## MVP Scope

MVP should use PostgreSQL-backed memory only:

- Project memory
- Organization memory
- Reusable validation rules
- Approved migration and code patterns
- Knowledge entries that reference metadata or artifacts

MVP should not include full vector memory, broad RAG over production data, or unmanaged document ingestion.

## Memory Scopes

| Scope | Purpose |
|---|---|
| Workflow memory | Current run decisions, assumptions, and intermediate outputs |
| Project memory | Project-specific architecture choices, source/target context, approvals |
| Organization memory | Reusable standards, naming conventions, accepted patterns |
| Template memory | Reusable template selections and configuration patterns |

## Retrieval Rules

- Retrieve only organization-scoped and project-scoped memory.
- Never retrieve another organization’s memory.
- Prefer approved patterns over draft agent output.
- Link memory entries to source artifacts, prompt versions, and approvals where possible.

## Future Vector Memory

Future vector memory may support embeddings, semantic retrieval, and RAG over approved knowledge entries. It must preserve tenant isolation, retention rules, audit logs, and data minimization.

