# Reconciliation Agent & Business Report

The recon agent produces a business-ready reconciliation deliverable from the
project's **approved** context (project context, architecture, validation
evidence, connector metadata, sprint output). **No row-level production data is
stored** — plans, code templates and high-level summaries only.

## Outputs

| API | Output |
|-----|--------|
| `POST /projects/{id}/recon/generate-plan` | `recon-plan` artifact — strategy, checks, scope, sign-off criteria |
| `POST /projects/{id}/recon/generate-code` | **draft** recon SQL/Python (`generated_code_artifacts`) — never executed; placeholders for credentials |
| `POST /projects/{id}/recon/generate-report` | `ReconReport` (markdown) rendered to **PDF** via reportlab |

Recon types covered: schema, row-count, checksum, null-count, duplicate,
business-rule, source-to-target aggregate, file-to-table, table-to-table.

## Report contents

Executive summary · source/target scope · checks performed · row-count summary ·
schema differences · mismatch summary · business-rule results · accepted
exceptions · risk summary · sign-off recommendation.

## Review

- `GET /projects/{id}/recon/reports`, `GET /recon/reports/{id}`.
- `POST /recon/reports/{id}/approve` / `/request-changes` (`agent:approve`).
- `GET /recon/reports/{id}/download` → PDF (regenerated on demand if missing).

## UI

`…/recon/reports` (generate plan/code/report + list) and
`…/recon/reports/{reportId}` (markdown report + approve/request-changes + PDF
download + "Send for sign-off"). Linked from the Recon page.
