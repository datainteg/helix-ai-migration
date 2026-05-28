# Worker / agents / connectors / sdk / cli / website cleanup — review-v5

Resumed `worker-cleanup-fixer` run. The prior (interrupted) run landed most of
the MEDIUM/LOW worker-side items in commit `c1248ae9`. This pass verified each
finding against the source and applied only what was still missing.

Scope: `worker/`, `agents/`, `connectors/`, `sdk/`, `cli/`, `website/`. No new
dependencies added.

## Per-finding status

| Finding | Status | Notes |
|---|---|---|
| Carryover — monolith terminal-state reconcile (`bmad_planning_workflow.py`) | ALREADY-DONE | Calls `persist_workflow_terminal_state_activity` on both the completed and failed exits via `reconcile_terminal_state`. |
| SC-052 — sha256 vendored BMAD scripts before subprocess (`bmad_loader.py`) | ALREADY-DONE | `_BMAD_SCRIPT_HASHES` manifest + `_script_checksum_ok` (fail-closed, `HELIX_BMAD_SCRIPT_HASH_ENFORCE` override). |
| SC-015 (connector-side) — postgres `hostaddr=` | ALREADY-DONE | `_connect_args` pins `host_ip`/`hostaddr` via psycopg2 `hostaddr`. |
| SC-015 (connector-side) — mysql host=ip | FIXED-NOW | `_build_connection_url` dials `host_ip` IP; `_connect_args` re-points TLS `server_hostname` to the real host for cert matching. |
| SC-015 (connector-side) — sqlserver host=ip | FIXED-NOW | URL host = pinned IP; adds ODBC `HostNameInCertificate=<real host>` when `Encrypt=yes` and `TrustServerCertificate=no`. |
| SC-015 (connector-side) — snowflake | FIXED-NOW (no-op by design) | Snowflake addresses by *account* over provider-controlled TLS; no rebindable hostname + no driver IP override. Added `_connect_args` that only forwards an explicit `host`/`host_ip` override (private-link case); documented why IP-pinning is intentionally inert. |
| M-003 — artifact_store secret threshold 16→12 + `org-` pattern | ALREADY-DONE | `_MIN_SECRET_VALUE_LEN = 12`; `org-` regex present. |
| M-008 — s3 read full CSV header line | FIXED-NOW | Replaced fixed `bytes=0-4096` GET with `_read_first_line` (growing 64 KiB ranged GETs until first `\n`, 1 MiB cap). Parquet/JSON column listing left as placeholder "data" column — proper inference needs `pyarrow` (forbidden new dep) → that sub-part SKIPPED. |
| M-009 — cache/dispose connector engines | ALREADY-DONE | postgres/mysql/sqlserver/snowflake all have lazy `_get_engine` + `close()` (`engine.dispose()`). |
| M-010 — per-node artifact path keyed by step | ALREADY-DONE | Keys by `f"{step_order:02d}:{agent_key}"`. |
| M-013 — validate token budget ≥4000 | ALREADY-DONE | `_token_budget` clamps up below `_MIN_TOKEN_BUDGET=4000`, warns below 6000. |
| M-018 — cli quote/validate domain | FIXED-NOW | RFC-1123 `_is_valid_domain` gate before interpolation; `CORS_ORIGINS` now built with `json.dumps([...])` instead of an f-string literal. |
| M-019 — module-level ThreadPoolExecutor | ALREADY-DONE | Shared `_HEARTBEAT_POOL` (lazy, locked, `atexit` drain). |
| L-001 — model_json_schema in prompt | ALREADY-DONE | `_build_system_prompt` emits `output_model.model_json_schema()` properties. |
| L-006 — csv row count without full load | FIXED-NOW | Streams line count (`sum(1 for _ in fh)` on the raw file) minus header instead of `pd.read_csv(path)`. |
| L-007 — log dropped frontmatter keys | ALREADY-DONE | `_safe_frontmatter` logs each denylisted key drop at INFO. |
| L-008 — tiktoken only if installed | ALREADY-DONE | `_estimate_tokens` keeps the len//4 heuristic with a documented "swap when tiktoken is added"; not installed → left as-is per instructions. |
| L-009 — cli subprocess returncode/stderr | FIXED-NOW | `_cmd_install` switched `subprocess.call` → `subprocess.run(check=False, stderr=PIPE, text=True)`; surfaces + quotes the captured stderr tail in the error message. (The BMAD-loader subprocess path already had returncode/stderr handling.) |
| L-010 — sdk narrow JSON except | FIXED-NOW | `_raise_for` now catches `(ValueError, json.JSONDecodeError)` (and guards non-dict bodies) instead of bare `except Exception`. |
| L-012 — website real 404 page | FIXED-NOW | New `website/src/pages/NotFoundPage.tsx`; `App.tsx` `*` route renders it (with `noindex` hint + title) instead of `<Navigate to="/">`. |

## Files changed this run

- `connectors/s3/connector.py` — M-008
- `connectors/files/csv_connector.py` — L-006
- `connectors/mysql/connector.py` — SC-015
- `connectors/sqlserver/connector.py` — SC-015
- `connectors/snowflake/connector.py` — SC-015 (documented no-op + override forwarding)
- `cli/helix_cli/__main__.py` — M-018, L-009 (+ moved `import re` to module scope)
- `sdk/python/helix_sdk/client.py` — L-010 (+ `import json`)
- `website/src/pages/NotFoundPage.tsx` (new) — L-012
- `website/src/App.tsx` — L-012

## Compile / test results

- `python -m py_compile` on all changed Python files + the (already-done)
  workflow/agents files: **PASS**.
- `pytest agents/tests -q`: **43 passed, 28 failed**. All 28 failures are
  pre-existing **environment** gaps, not regressions:
  - Sandbox Python is **3.10.5**, so `import tomllib` (3.11+ stdlib) fails in
    `bmad_loader.py`'s fallback path (untouched).
  - `langgraph` is not installed, so `agents/bmad/graph.py` import fails.
  The static-analysis suite and the budget/provider suites that don't hit those
  imports pass. None of the failures trace to files edited this run.
- SDK TS — `cd sdk/typescript && npx -p typescript tsc --noEmit`: **exit 0**.
- Website — `cd website && npx tsc --noEmit`: **exit 0**.

## Skipped / deferred

- **M-008 parquet/JSON column inference** — needs `pyarrow` (new dep, forbidden).
  Left the existing single-column "data" placeholder. CSV header read is fixed.
- **SC-015 Snowflake true IP-pin** — not applicable (account-based addressing,
  provider TLS, no driver IP override). Handled as a documented no-op.
