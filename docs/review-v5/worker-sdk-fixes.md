# Worker / Agents / Connectors / SDK fixes (review-v5)

Branch: `upgrade/review-and-fix`
Scope: CRITICAL + HIGH findings in `worker/`, `agents/`, `connectors/`, `sdk/`, `cli/`.
No new dependencies were added. No architecture changes.

## Files changed

- `worker/activities/bmad_node_activities.py`
- `worker/workflows/bmad_per_node_workflow.py`
- `worker/main.py`
- `agents/runtime/providers/bedrock_provider.py`
- `agents/runtime/bmad_executor.py`
- `connectors/s3/connector.py`
- `sdk/python/helix_sdk/client.py`
- `sdk/typescript/src/index.ts`

## Per-finding status

### C-002 (worker side) — Temporal completions never reconciled to DB — FIXED
- Added `persist_workflow_terminal_state_activity(state_data: dict)` in
  `worker/activities/bmad_node_activities.py`. It opens the worker-local
  `SessionLocal`, looks up `WorkflowRun` by `workflow_id` (unique column), and
  sets `status`. On DB error it logs + rolls back + swallows (does NOT re-raise)
  so a permanent DB failure can't trap the activity in infinite Temporal retries.
- `BMADPerNodeWorkflow.run` now wraps the whole pipeline in try/except and calls
  the new activity at every exit:
  - normal completion → `completed`
  - approval timeout → `expired`
  - rejection signal → `rejected`
  - any unhandled exception (incl. H-007 `ApplicationError`) → `failed` with
    `summary={"error": ...}`, then re-raises so Temporal still records failure.
- Registered the activity in `worker/main.py` import block + `activities=[...]`.
- Note: the activity takes a single `state_data: dict` arg (matches the existing
  `persist_workflow_step_activity(step_data: dict)` convention) rather than the
  loose positional signature in the audit prose. Keys: `workflow_id`, `status`,
  `summary`.

### H-007 — `run_step` swallowed BMAD failure into next phase — FIXED
- After the persist-step activity, `run_step` checks `result.get("success")`.
  If False it raises `ApplicationError(..., non_retryable=True)`. The step is
  still persisted as `failed` first; the outer try/except then reconciles the
  run to `failed` (C-002) before re-raising. Downstream phases no longer run on
  `None` upstream context.

### H-006 — Bedrock Llama 3+ prompt template wrong — FIXED
- `agents/runtime/providers/bedrock_provider.py` `_build_body` now branches:
  - `meta.llama3-*` / `meta.llama4-*` → chat template
    `<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n`,
    `max_gen_len`.
  - legacy `meta.llama2-*` (and other `meta.*`) → `<s>[INST]…[/INST]`, `max_gen_len`.
  - `mistral.*` → `[INST]…[/INST]` (no surrounding `<s>`), `max_tokens`.
- `anthropic.*`, `cohere.*`, `amazon.*`, `deepseek.*`/`openai.*` branches untouched.

### H-012 — Per-agent LLM routing dead code in PydanticAI path — FIXED
- `_resolve_provider_for_org(org_id, agent_code: str = "bmad-agent")` now forwards
  `agent_code` to `resolve_routing(...)` instead of the literal `"bmad-agent"`.
- `_try_pydantic_ai` passes `agent.code` (e.g. `bmad-agent-architect`) through.
  Per-agent model mappings configured in the admin UI are now honoured on the
  preferred PydanticAI transport. Default preserves legacy behaviour for any
  caller that omits `agent_code`.

### H-013 — S3Connector client not cached + opaque NoCredentialsError — FIXED
- `S3Connector.__init__` adds `self._client = None`; `_get_client` builds the
  boto3 S3 client lazily and caches it on the instance (reused across
  list_schemas/list_tables/list_columns within one connector lifetime).
- `sts.assume_role(...)` is wrapped in `try/except botocore.exceptions.NoCredentialsError`
  and re-raised as
  `ConnectionError("S3 connector requires either ambient IAM credentials in the worker container, or explicit access_key_id + secret_access_key in the connector config.")`.

### H-011 — SDK `.list()` silently caps; no pagination helper — FIXED
- Python (`sdk/python/helix_sdk/client.py`): added module-level `_paginate_all()`
  offset-walker (guarded by `max_pages=100`). Added `list_all()` /
  `list_all_for_project()` to `_Projects`, `_Workflows`, `_Cutovers`, `_Artifacts`.
  `paginated()` helpers now accept `offset`. `.list()` docstrings document the cap.
  `total` was already exposed via the existing `PaginatedResponse`/`paginated()`.
- TypeScript (`sdk/typescript/src/index.ts`): added `paginateAll()` helper and
  `listAll()` / `listAllForProject()` on `Projects`, `Workflows`, `Cutovers`,
  `Artifacts`. `paginated()` accept `offset`.
- Reality adjustments (verified against backend routers):
  - `Templates`: `/migration-templates` returns a static bare-array catalog with
    NO server-side `limit`/`offset`. `list_all()`/`listAll()` kept for symmetry
    but return the full catalog in one synthesised page (no fake query params).
  - `Knowledge`: `/knowledge/search` is a relevance-ranked top-N endpoint
    (server caps `limit` at 20, NO `offset`). Did NOT add `search_all`/`searchAll`
    (would 422 / be meaningless). `search()` docstring documents the top-N cap;
    `search_paginated()` retained as an envelope-shaped convenience.
  - `Projects` (limit≤200), `Workflows`/`Cutovers`/`Artifacts` (limit≤200) all
    support `offset`, so the offset-walker is real for those.

### CLI — SKIPPED (no CRITICAL/HIGH in scope)

### M-019 (ThreadPoolExecutor per call) — SKIPPED (MEDIUM, explicitly out of scope)

## Signatures backend / frontend should track

- NEW worker activity: `persist_workflow_terminal_state_activity` on task queue
  `helix-bmad-task-queue`. Backend does not call it directly (the per-node
  workflow does), but anyone enumerating registered activities should know it
  exists. It updates `WorkflowRun.status` to `completed|failed|rejected|expired`
  by `workflow_id`.
- Behaviour change visible to frontend/SSE: per-node Temporal runs now reach a
  terminal `WorkflowRun.status` instead of being stuck at `started`, so the SSE
  loop in `agent_workflows.py` will close on success/failure rather than timing
  out at 120s. No API contract change.
- H-007 behaviour change: a failed BMAD step now fails the whole workflow
  (status `failed`) instead of continuing. Frontend should already handle the
  `failed` terminal status.

## Compile / lint results

- `python -m py_compile` — OK for all 7 changed Python files.
- `python -m ast.parse` — OK for all changed Python files.
- pyflakes / ruff / flake8 not installed in this environment; not run.
- Python SDK import smoke test — OK; `_paginate_all` unit-exercised (250-row /
  total=None / single-page cases all terminate correctly).
- `agents/tests/test_provider_adapters.py` — 14 passed (incl. Bedrock); Bedrock
  Llama3 / Llama2 / Mistral template branches verified by inline assertion.
- TypeScript: `npx -p typescript@5.4 tsc --noEmit` (transient, not a project dep)
  — exit 0, no errors. Existing `tests/pagination.test.ts` references only
  preserved methods. Jest not run (would require installing devDeps).

## Follow-up / notes

- `temporalio` is not installed in this dev environment, so the per-node
  workflow could not be imported here. `from temporalio.exceptions import
  ApplicationError` is the canonical public path and `temporalio>=1.8.0`
  (worker/requirements.txt) supports `ApplicationError(non_retryable=...)`.
  Verify on the worker container / CI where temporalio is present.
- The audit also lists C-002 on the BACKEND side
  (`workflow_service.py:80-95, 200-220`) — the backend still needs the
  `_persist_started_workflow` / `_persist_workflow_result` cleanup (C-001 / the
  start-path reconcile). That is owned by the backend agent and was NOT touched
  here. The worker-side terminal-state activity is the other half of the fix.
- Knowledge search has no offset paging server-side; if true "fetch all matches"
  is ever needed it requires a backend endpoint change (out of scope).
- The monolithic `BMADPlanningWorkflow` was left unchanged — the audit's C-002
  fix target was the per-node workflow; adding terminal reconcile to the
  monolith would be a separate additive change.
