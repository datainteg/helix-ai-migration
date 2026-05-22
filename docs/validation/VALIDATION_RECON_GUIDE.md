# Validation and Reconciliation Guide

Helix Migration validation and reconciliation help teams confirm that migration results are complete, accurate, and explainable.

## Validation Types

| Type | Purpose |
|---|---|
| Schema validation | Compare source and target structure |
| Row count validation | Compare record counts |
| Null checks | Detect unexpected nulls |
| Duplicate checks | Detect duplicate keys or rows |
| Distribution checks | Compare value distribution |
| Checksum checks | Detect content mismatch efficiently |
| Custom rules | Support project-specific checks |

## Schema Validation

Schema validation should compare:

- Schema names
- Table names
- Column names
- Data types
- Nullability
- Primary keys
- Required constraints

Result should show:

- Missing target tables
- Extra target tables
- Missing columns
- Type mismatches
- Nullable mismatches
- Constraint mismatches

## Row Count Validation

Row count validation compares source and target counts.

Store:

- Source count
- Target count
- Difference
- Difference percentage
- Status
- Timestamp

## Null Checks

Null checks detect unexpected nulls in important columns.

Rule fields:

- Table
- Column
- Allowed null threshold
- Severity
- Owner

## Duplicate Checks

Duplicate checks detect:

- Duplicate primary keys
- Duplicate business keys
- Duplicate full rows when configured

Store only summary details by default.

## Distribution Checks

Distribution checks compare:

- Min and max
- Average
- Distinct count
- Top values
- Bucketed distribution

Use summaries to avoid storing raw production data.

## Checksum Strategy

Checksum checks can compare deterministic hashes across source and target.

Recommended:

- Use stable column ordering.
- Normalize null handling.
- Normalize whitespace only when configured.
- Use partitioned checksums for large tables.
- Store checksum summaries, not raw rows.

## Mismatch Reporting

Mismatch reports should include:

- Source reference
- Target reference
- Rule type
- Severity
- Summary
- Sample identifiers only when allowed
- Recommended next action

Avoid storing raw sensitive values by default.

## AI Mismatch Explanation

AI can summarize mismatch patterns:

- Likely cause
- Impact
- Recommended owner
- Suggested fix
- Confidence

AI explanations must be based on stored summaries and metadata unless explicit data access is configured.

## Report Format

Reports should include:

- Project name
- Run timestamp
- Source and target summary
- Validation status
- Reconciliation status
- Failed checks
- Risk summary
- AI explanation
- Approval status
- Export metadata

Suggested status values:

- Passed
- Passed with warnings
- Failed
- Needs review
- Cancelled

## Tooling

Validation engine may integrate:

- Great Expectations
- Soda Core
- dbt tests
- Custom reconciliation engine

The custom engine should provide the metadata-first checks needed for MVP.

## Developer Execution Integration

Generated code and generated notebook drafts should link to validation and reconciliation plans.

Rules:

- Generated code should include assumptions and validation requirements.
- Generated notebooks should include validation cells when the target format supports them.
- Code conversion outputs should identify required validation checks before approval.
- DAG review outputs should feed the migration readiness score.
- Artifact approvals should reference validation requirements when generated code affects migration execution.

Developer execution validation examples:

- A Python-to-Databricks notebook draft should include row count and schema validation cells where applicable.
- A SQL-to-dbt-style model draft should list expected tests such as not-null, uniqueness, and accepted-values checks.
- A DAG review should report cycles, duplicate task IDs, risky sensors, missing retries, and missing timeouts.

## Validation Templates and Observability

Validation templates should include schema compare, row count, null checks, duplicate checks, distribution checks, checksum checks, and source-to-target reconciliation templates.

Generated code should link to validation plans. Generated notebooks should include validation cells. Recon results should be exportable as PDF, Markdown, JSON, CSV, HTML, and report artifacts where supported.

Validation metrics should feed observability:

- Runtime duration
- Rows checked
- Failed rules
- Warning count
- Error count
- Connector latency

AI mismatch explanations are draft explanations and must be reviewed by humans before production decisions.
