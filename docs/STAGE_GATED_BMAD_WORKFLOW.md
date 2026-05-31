# Stage-Gated BMAD Migration Lifecycle

Helix converts the linear BMAD pipeline into an enterprise **stage-gated
execution lifecycle**: each stage runs an agent, produces a reviewable artifact,
and waits for human approval before the next stage can start. The lifecycle is
driven by a **DB state machine** (`migration_stages`) — not one long-lived
Temporal workflow — so each stage is a short agent run and approval is an
API/DB action.

## The 13 stages

| # | Stage | Agent (persona) | Optional | Artifact |
|---|-------|-----------------|----------|----------|
| 1 | PROJECT_CONTEXT | Winston (architect) | no | project-context |
| 2 | BUSINESS_ANALYSIS | Mary (analyst) | no | business-analysis |
| 3 | ARCHITECTURE | Winston (architect) | no | architecture |
| 4 | PROJECT_PLANNING | John (PM) | no | project-plan |
| 5 | UX_DESIGN | Sally (UX) | **yes** | ux-plan |
| 6 | SPRINT_GENERATION | John (PM) | no | sprint-plan |
| 7 | SPRINT_EXECUTION | orchestration | no | — |
| 8 | DEVELOPMENT | Amelia (dev) | no | implementation-plan |
| 9 | VALIDATION | QA | no | validation-plan |
| 10 | RECONCILIATION | Recon | no | recon-plan |
| 11 | SIGN_OFF | human | no | signoff |
| 12 | DOCUMENTATION | Paige (tech writer) | no | final-docs |
| 13 | CLOSURE | system | no | closure-report |

Stage keys + agent mapping live in `backend/app/services/lifecycle_constants.py`.

## Stage statuses (state machine)

`not_started → running → generated → under_review → (approved | rejected |
edit_requested)`; `edit_requested → resubmitted → …`; optional stages may be
`skipped`. Done = `{approved, completed, skipped}`.

## Gating rules

- A stage cannot **start / submit / generate / approve** until the closest
  preceding **required** stage is done (`_require_prior_done`). Optional stages
  left `not_started` are non-blocking.
- `start` only from `{not_started, rejected, edit_requested, failed}` — a closed
  gate can never be reset to `running`.
- `resubmit` only from `{rejected, edit_requested}`.
- VALIDATION can be approved only once ≥1 validation evidence item is accepted.
- SPRINT_GENERATION-derived sprints cannot start execution until the sprint plan
  is approved.

## Agent execution

`POST /projects/{id}/stages/{key}/run-agent` runs the mapped persona over the
project's **approved** artifacts (`stage_agent_service`), stores the output as a
`migration_artifact` v1, and parks the stage at `under_review`. `regenerate`
appends a new version; `continue-after-approval` advances and auto-runs the next
agent stage. Agent runs reuse the existing BMAD executor (`execute_agent_skill`)
with `persist_file=False` (DB is the source of truth; the backend's artifact
volume is read-only).

## RBAC + separation of duties

- Running/submitting/editing → `project:write`.
- Approving/rejecting/requesting-changes → `agent:approve`.
- **Separation of duties:** the user who submitted a stage for review cannot
  approve it unless they are an `admin`/`super_admin`.

## Audit

Every transition is appended to `stage_transition_logs` (domain audit) **and**
the security `audit_logs`, and emits a best-effort notification. The per-project
timeline is exposed at `GET /projects/{id}/lifecycle/transitions` and rendered on
the Audit tab.

## Legacy fallback

The original linear `HelixBMAD` workflow is untouched and remains available as a
fallback. A project opts into the stage-gated lifecycle via
`projects.use_stage_gated_lifecycle` (set true when the lifecycle is initialized
on create).

---

## Security review (enforced)

| Rule | How it is enforced |
|------|--------------------|
| No code execution in backend | Generated code is stored as draft data; the API/worker never run it. Optional code-server runs in an isolated container (see [WORKSPACE.md](../WORKSPACE.md)). |
| Secrets not logged / exposed | Connector secrets stay encrypted; only `connector_type`/`name`/masked preview reach prompts. SMTP secrets handled by the email-settings service. Artifact frontmatter is scrubbed (SEC-011). |
| Artifacts project-scoped | Every query filters `organization_id` + `project_id`; cross-org access 404s (covered by `test_organization_isolation`). |
| Approval audited | `approve_stage`/artifact approval write transition + audit rows. |
| Sign-off audited | Draft/send/approve/reject all audited. |
| No row-level production data | Validation evidence, recon reports and summaries store results/metadata only. |
| Generated code draft until approved | `generated_code_artifacts.status` starts `draft`; review → approve. |

## Tests

`backend/tests/test_stage_gated_lifecycle.py` covers alias uniqueness, lifecycle
init, gating, optional-skip, artifact v1/v2/approval/resubmit, transition logs,
sprint-generation gating, validation evidence, recon report, sign-off draft, and
organization isolation.
