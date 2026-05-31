# Artifact Review Lifecycle

Stage documents are stored as **markdown-in-DB** `migration_artifacts` with full
version history and a review thread — distinct from the file-based
`code_artifacts`.

## Versioning

- The agent creates **v1** (`created_by_type=agent`, status `generated`).
- A user edit creates a **new version** (`edit_artifact_version`) — history is
  never overwritten. `(artifact_id, version_number)` is unique; concurrent
  inserts retry under a savepoint.
- Editing an **approved** artifact re-opens it as `resubmitted` while leaving the
  approved version row intact.

## Review actions

| Action | Effect |
|--------|--------|
| Submit for review | status → `under_review` |
| Approve | status → `approved`, locks `current_version_id` to the reviewed version |
| Request changes | status → `changes_requested` |
| Reject | status → `rejected` |
| Comment | threaded comment on the artifact/version |

Every review action validates that the supplied `version_id` belongs to the
artifact (no cross-artifact corruption) and records a `migration_artifact_reviews`
row.

## Compare

`GET /migration-artifacts/{id}/compare?from_version=&to_version=` returns a
unified diff plus added/removed line counts. The UI renders it side-by-side.

## UI

- `…/lifecycle` — stage timeline + next action.
- `…/lifecycle/{stageKey}` — objective, input context, generated artifact,
  version history, comments, full action panel.
- `…/artifacts/{artifactId}/review` — 3-pane versions / viewer-editor / review.
- `…/artifacts/{artifactId}/compare` — version diff.

## API

`/api/v1/projects/{id}/migration-artifacts`, `/migration-artifacts/{id}`,
`/versions`, `/submit-review`, `/approve`, `/reject`, `/request-changes`,
`/comments`, `/compare`. Reads need an org member; create-version/submit need
`project:write`; approve/reject/request-changes need `agent:approve`.
