# Dependency-gated fixes (review-v5)

Branch: `upgrade/review-and-fix`
Scope: `connectors/`, `agents/`, and their dependency manifests only. The user
APPROVED adding the two previously-blocked dependencies (`pyarrow`, `tiktoken`).
Both are ADDITIVE and degrade gracefully — a missing wheel never breaks module
import.

## Findings addressed

### M-008 — S3 parquet column inference (`pyarrow`)
- File: `connectors/s3/connector.py`.
- `list_columns` previously returned a placeholder `"data"` column for parquet.
  It now calls the new `_infer_parquet_columns(...)`, which reads the REAL
  parquet schema via `pyarrow.parquet.read_schema` and maps each field to the
  connector's `ColumnInfo` shape (`column_name`, `data_type=str(field.type)`,
  `is_nullable`, `ordinal_position`).
- `read_schema` is given a new `_S3RangeFile` — a minimal seekable, read-only
  file-like backed by S3 ranged GETs (`Range: bytes=start-end`) with the object
  size resolved once via `head_object`. pyarrow seeks to the footer/metadata, so
  only a few small ranges are fetched — NOT the whole (potentially multi-GB)
  object.
- `pyarrow` is **lazy-imported inside** `_infer_parquet_columns`. If it is
  missing, a clear `DiscoveryError` is raised ("pyarrow not installed …") while
  the rest of the connector — module import, `test_connection`, `list_schemas`,
  `list_tables`, and CSV/JSON inference — keeps working.
- A `except DiscoveryError: raise` guard was added before the generic
  `except Exception` in `list_columns` so the actionable pyarrow message is not
  re-wrapped into a generic "Column inference failed".

### L-008 — token estimate via `tiktoken`
- File: `agents/runtime/bmad_executor.py`.
- `_estimate_tokens` now prefers `tiktoken` (encoding `cl100k_base`) for an
  accurate BPE count and falls back to the original `len // _CHARS_PER_TOKEN`
  (4) heuristic when tiktoken is unavailable or encoding/encode fails.
- New `_get_tiktoken_encoding()` lazy-imports tiktoken in a try/except and caches
  the result module-level (`None` = unresolved, `False` = unavailable → use
  heuristic, encoding object = available) so the import/load cost is paid at most
  once. tiktoken is **never imported at module load**, so a missing wheel cannot
  break importing the executor.

## Were the libs already present?
- `tiktoken==0.13.0` was **already in both lock files transitively** (via
  `pydantic-ai-slim`): `worker/requirements.lock:561` and
  `backend/requirements.lock:692`. It was NOT a direct dependency. It was NOT
  installed in the local dev venv.
- `pyarrow` was **not present** anywhere — not in either lock file, not in the
  local venv (pandas 2.2.3 is installed but did not pull pyarrow on this
  platform).

## Requirements files changed (and pins)
- `backend/requirements.txt` — added `pyarrow>=18.0.0` (M-008; connectors run in
  the backend image — `backend/app/services/connector_service.py` imports
  `S3Connector`). A `>=` floor matches the existing direct-dep style.
- `backend/requirements.lock` — added `pyarrow==24.0.0` (`# via -r
  backend/requirements.txt`), inserted alphabetically after `py-key-value-aio`.
- `worker/requirements.txt` — added `tiktoken>=0.7.0` (L-008; agents runtime
  ships in the worker image). It is already pulled transitively by
  pydantic-ai-slim; pinned here as an explicit direct dep.
- `worker/requirements.lock` — updated the existing `tiktoken==0.13.0` entry's
  `via` block to also list `-r worker/requirements.txt` (now a direct dep).

Note: the worker Dockerfile also copies `connectors/`, but the worker never
invokes connector discovery (no references to `connector_service` /
`list_columns` / `S3Connector` under `worker/`), so `pyarrow` is added to the
backend image only. If parquet inference were ever triggered there, it degrades
gracefully to a clear `DiscoveryError`.

## py_compile
- `python -m py_compile connectors/s3/connector.py agents/runtime/bmad_executor.py` → OK.

## Smoke tests
Both libs were installed locally for testing (pyarrow 24.0.0, tiktoken 0.13.0 —
matching the lock pins).

Real code paths (libs present):
- `_estimate_tokens("The quick brown fox jumps over the lazy dog.")` → 10
  (tiktoken cl100k_base loaded); `_estimate_tokens("")` → 1.
- Generated a 1-row parquet in memory, served it through a fake S3 client that
  asserts ranged GETs: schema read returned columns
  `id:int64, name:string, score:double, active:bool` with correct nullability
  and ordinal positions; the non-ranged `get_object` path was never used.
- Generated a 1.15 MB / 40-row-group parquet: schema read fetched only 64 KB
  (5.7% of the file) via a single ranged GET — confirming it does NOT download
  the whole object.

Fallback code paths (libs forced absent via a blocking importer):
- `agents.runtime.bmad_executor` imports fine without tiktoken;
  `_estimate_tokens("a"*40)` → 10 (heuristic); `_get_tiktoken_encoding()` →
  `None`.
- `connectors.s3.connector` imports fine without pyarrow; the parquet path raises
  `DiscoveryError("pyarrow not installed …")`; CSV inference
  (`id,name,email`) still works (no regression).

The full test suite was not run, per instructions.
