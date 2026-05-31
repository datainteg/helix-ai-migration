# Validation Evidence & QA Agent

Helix generates validation test cases + expected evidence; the **developer runs
the tests in their own environment and uploads results**. Helix stores test
results/metadata only — **no row-level production data**.

## Upload

`POST /projects/{id}/validation/evidence` (multipart): a `title`,
`evidence_type` (`summary|test_result|json|log|screenshot`), an optional markdown
summary, optional result JSON, and an optional file (≤25 MB, written to a
dedicated evidence directory, never executed; metadata-only if the path is
read-only).

## QA Agent review

`POST /validation/evidence/{id}/qa-review` runs the QA agent over an evidence
item and stores a `validation-review` artifact covering test coverage, failed
tests, missing evidence, data-quality risks, deployment readiness, and overall
completeness with a recommendation.

## Accept / reject

- `POST …/{id}/accept` (`agent:approve`) → status `accepted`.
- `POST …/{id}/reject` (`agent:approve`) → status `rejected`.

The **VALIDATION lifecycle stage can be approved only once ≥1 evidence item is
accepted** (`has_accepted_evidence` gate).

Statuses: `uploaded → under_review → accepted | rejected | changes_required`.

## UI

`…/validation/evidence` (upload form + evidence table) and `…/validation/review`
(QA review queue with the review markdown). Links from the existing Validation
page.
