# Sprint Generation & Execution

Sprints are generated **from approved planning artifacts only** — never mock
data.

## Generation

`POST /projects/{id}/sprints/generate` requires the four planning stages
(PROJECT_CONTEXT, BUSINESS_ANALYSIS, ARCHITECTURE, PROJECT_PLANNING) to be
**approved**, then:

1. runs the sprint-planner agent (SPRINT_GENERATION stage) over the approved
   context,
2. parses the markdown plan into structured `sprints` + `sprint_tasks`
   (`parse_sprint_plan_to_structured_tasks`), and
3. persists them linked to the source artifact (`created_from_artifact_id`).

If the agent output is not parseable, it falls back to the canonical 6-phase
migration template (Source Discovery → Schema Mapping → ETL/Conversion →
Validation → Reconciliation → Cutover/Sign-off) — standard methodology, derived
from the project, not demo data. Re-generation replaces prior **planning**
sprints without duplicating; active sprints survive.

## Approval gate

The sprint plan is approved by approving the **SPRINT_GENERATION** lifecycle
stage (separation of duties + audit reused):

- `POST /projects/{id}/sprints/submit-review`
- `POST /projects/{id}/sprints/approve` (`agent:approve`)
- `POST /projects/{id}/sprints/request-changes`

`POST /projects/{id}/sprints/{sprintId}/start` activates a sprint and is
**blocked until the sprint plan is approved**.

> The legacy mock seed endpoint (`/sprints/seed`) now returns **410 Gone** — use
> `/generate`.

## UI

The Sprints dashboard "Generate sprints" button drives generation (and surfaces
the gating error if planning isn't approved). The board, mapping canvas,
timeline, risks and approval pages render the real generated data. Sprint-plan
review is also reachable on the Lifecycle → Sprint Generation stage.

## Task model

`sprint_tasks` carry type (`migration|validation|recon|schema_mapping|
data_profiling|code_review|…`), status (kanban columns), owner kind
(human/agent), `ai_agent`, story points and dependency/artifact links.
