# Governance and Audit

## Purpose

Governance and audit give Helix Migration enterprise traceability across users, agents, approvals, prompts, artifacts, exports, validation, and reconciliation.

## Audit Logs

Audit logs should record:

- User login/logout and failed login
- User, role, and organization changes
- LLM provider setup and key rotation
- Project and subproject changes
- Connector setup and schema scans
- Artifact upload, analysis, conversion, approval, rejection, and export
- Validation and reconciliation runs
- Report exports
- Plugin install/enable/disable

Audit logs should be append-only where possible.

## Approval History

Approval history should track:

- Migration plan approvals
- Architecture approvals
- Validation plan approvals
- Generated artifact approvals
- Rejections and requested changes
- Approver, timestamp, notes, and linked artifact/output version

## Prompt and Model History

Store prompt version, model provider, model name, agent type, execution status, token usage, and latency. Do not store secrets in prompt logs.

## Agent Decision Logs

Agent decision logs should capture a concise reasoning summary, assumptions, risks, confidence score, input references, and output references.

## Artifact History

Artifact history should include source version, generated version, hashes, storage location, review status, approval status, and lineage.

## Exportable Audit Report

Audit reports should be exportable as Markdown, PDF, JSON, CSV, or HTML where supported.

