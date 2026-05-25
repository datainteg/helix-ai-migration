## Agents + Worker Code Review

> Generated 2026-05-26. Scope: agents/ (excl. BMAD-METHOD vendored copy) + worker/ + _bmad/scripts/.

Severity legend: CRITICAL, HIGH, MED, LOW.

---

## 1. High-level architecture

### 1.1 Shared `agents/` package

The `agents/` package is the single import surface used by both:

- the **backend** (FastAPI), which calls `HelixBMAD(...).run()` synchronously (dev/test) or schedules `HelixBMAD(...).start_temporal()` for production, and
- the **Temporal worker** (`worker/main.py`), whose activities import `agents.bmad.graph.run_bmad_graph` and `agents.runtime.bmad_executor.execute_agent_skill`.

Both processes also import the SQLAlchemy ORM models from `app.models.*` for persistence — but they instantiate **independent engines** via separate `SessionLocal` factories (`app.db.session.SessionLocal` for the backend, `worker.db.session.SessionLocal` for the worker). This is the GAP-8 decoupling called out in the worker session docstring. It is partial: `agents.runtime.bmad_executor._resolve_provider_for_org` and `agents.runtime.llm_client.call_llm` still import `app.db.session.SessionLocal`, which means **the worker still drags backend DB wiring in any time an org-scoped LLM call resolves credentials.** Worth a follow-up but not a defect — see Section 3.

### 1.2 `HelixBMAD` facade vs `run_bmad_graph`

`agents.helix.HelixBMAD` is a thin class wrapper around the lower-level functional API in `agents.bmad.graph` + `agents.runtime.bmad_executor` + `agents.runtime.artifact_store`. The facade exposes:

- `.run()` — sync, in-process LangGraph execution.
- `.start_temporal()` / `.resume()` / `.get_temporal_status()` — async Temporal handles.
- `.review_artifact(...)` — ad-hoc single-file BMAD code review/analysis (used by the Developer Workspace `/artifacts/{id}/review|analyze` endpoints).
- `.list_artifacts()` / `.get_artifact()` — read-side access.

`run_bmad_graph` is the underlying functional entry point — it builds the compiled LangGraph once, invokes it on a fresh initial state, then computes a final `status` from the post-conditions (errors → failed, decision==rejected → rejected, decision==approved+tech_writer present → completed, decision==None+gate output → pending, else running).

### 1.3 Provider registry pattern (10 adapters)

`agents/runtime/providers/` houses one file per LLM backend. `base.py` defines `BaseProvider`, `CallContext`, and a module-level `_REGISTRY: dict[str, BaseProvider]`. `__init__.py` imports each adapter class and calls `register_provider(_cls())` at import time. The dispatcher (`agents.runtime.llm_client.call_llm`) just calls `get_provider(provider_type).call(ctx)`.

Adapters cover: `openai`, `anthropic`, `google` (Gemini direct API), `deepseek`, `openrouter`, `bedrock`, `vertex`, `azure`, `custom` (OpenAI-compatible mirror), `local` (Ollama/LM Studio default).

Common conventions:

- Synchronous `httpx.post` (NO async). Lazy-import of `httpx` and any SDK (boto3, openai, vertexai) inside `_call` so missing deps don't blow up at module import.
- Return `parse_text_to_dict(content)` — best-effort JSON extraction via `safe_extract_json`, falling back to `{"summary": content}`.
- Return `None` on non-2xx or transport error; `safe_call` catches every `Exception` and logs at WARNING.

### 1.4 LangGraph state shape + node flow (13 steps)

`agents/bmad/state.py` defines `BMADWorkflowState` (a `TypedDict`) with identifiers, status, errors, the inputs (`requirement_text`), the artifact-store key (`artifact_dir`), per-agent artifact paths, per-agent compact outputs, and the approval-gate fields.

Graph edges (`agents/bmad/graph.py`):

```
START
  → winston_project_context        (Phase 0: shared-memory bootstrap)
  → mary_analyze                   (Phase 1)
  → john_prd                       (Phase 2)
  → sally_ux
  → winston_architecture           (Phase 3)
  → winston_stories
  → winston_readiness
  → approval_gate                  (conditional)
    ├─ approved → amelia_story → amelia_dev → amelia_qa
    │             → amelia_code_review → paige_docs → END
    └─ else     → END
```

Every node delegates to `_run(...)` which calls `execute_agent_skill(...)` then either `_apply_result` or `_apply_error`.

### 1.5 File-based artifact handoff

BMAD's communication contract is file-based, not in-memory. Each agent writes a markdown artifact with YAML frontmatter to:

```
{planning_artifacts}/{project_id}/{agent_code}/{YYYYMMDDTHHMMSSZ}-{slug}.md
```

A `latest.json` index in each `{agent_code}/` directory maps slug → latest filename so `read_latest()` is O(1). Writes are atomic (tempfile + `os.replace`). The store also mirrors `bmad-generate-project-context` output to a stable `project-context.md` path so the BMAD `persistent_facts` glob resolves it.

`collect_prior_context(project_id, upstream_agents=...)` is the read-side helper a downstream node uses to assemble its user prompt context.

### 1.6 Temporal workflows: planning vs per-node

Two workflows are registered on the same `helix-bmad-task-queue`:

- **`BMADPlanningWorkflow`** — monolithic; one activity (`execute_bmad_graph_activity`) wraps the whole 13-node LangGraph. Simple, but no per-step retries, no per-step persistence, no signal-based approval.
- **`BMADPerNodeWorkflow`** — 13 activities + `persist_workflow_step_activity`; signal-driven approval gate via `workflow.wait_condition(...)` (48-hour timeout); queries for `current_step`, `outputs`, `artifact_paths`. This is the workflow `HelixBMAD.start_temporal()` actually submits.

Workflow modules use `with workflow.unsafe.imports_passed_through():` to escape the Temporal determinism sandbox when importing activity functions (necessary because activities indirectly pull in `httpx`, `yaml`, `subprocess`).

### 1.7 Worker DB decoupling (`worker/db/session.py`)

The worker maintains its own `create_engine` against `DATABASE_URL` with a small pool (3 + 2 overflow) and `pool_pre_ping=True`. The docstring explicitly calls out that the worker no longer borrows `app.db.session.SessionLocal` — this is the GAP-8 fix. But see Section 3 — `agents.runtime.llm_client.call_llm` and `bmad_executor._resolve_provider_for_org` still import the backend session module.

### 1.8 BMAD loader

`agents.runtime.bmad_loader` is the bridge to the vendored `agents/bmad/BMAD-METHOD/` tree:

- `load_bmad_config()` — invokes `_bmad/scripts/resolve_config.py` via subprocess; falls back to in-process 4-layer TOML merge if the script is missing/broken. Cached with `lru_cache(maxsize=1)`.
- `load_bmad_agent(code)` / `load_bmad_skill(name)` — same pattern but invokes `resolve_customization.py`. Cached with `lru_cache`.
- `build_persona_prompt(agent)` — extracts the `## Overview` section from SKILL.md plus customization layers (role/identity/communication_style/principles/persistent_facts).
- `build_skill_instructions(skill)` — strips the SKILL.md YAML frontmatter and returns the markdown body.

This gives Helix a "skill index" in memory: every BMAD agent + every BMAD skill resolves to an in-memory dataclass with the full SKILL.md body and the merged customize.toml.

---

## 2. File-by-file review

### 2.1 `agents/__init__.py`

Three lines re-export `HelixBMAD` + `HelixBMADResult`. Nothing to review beyond confirming `__all__` is wired (it is).

### 2.2 `agents/helix.py`

`HelixBMAD` is the user-facing facade.

- LOW — Line 116: `os.getenv("TEMPORAL_ADDRESS", self.DEFAULT_TEMPORAL_ADDRESS)` is read at `__init__` time. If the env var changes between Helix instances in a long-lived process (rare), the change isn't picked up. Acceptable — this is the conventional pattern.
- LOW — `workflow_id` is `f"bmad-{project_id}-{requirement_id}"`. No sanitisation, so a `project_id` containing `/` or whitespace would produce an invalid Temporal workflow ID. The artifact store calls `_slug(project_id)`, but the workflow ID does not. Temporal will accept most strings but reject control chars; consider an explicit slug pass here.
- LOW — `start_temporal()` opens a fresh `Client.connect(self.temporal_address)` every call. Connection pooling would be nicer, but Temporal client is light. Same comment applies to `resume()` + `get_temporal_status()`.
- LOW — `start_temporal()` returns `run_id=handle.result_run_id`. `result_run_id` is `Optional[str]` (None when workflow hasn't actually started yet). Result is fine in practice — `start_workflow` blocks until the start request is acknowledged — but a defensive `or ""` would silence a possible mypy warning.
- MED — `review_artifact()` truncates `source_code` to 8000 chars at line 258 with no warning to the caller and no token-budget interaction. Pasting a 200KB file silently drops 96% of it. Worth surfacing a `truncated=True` flag in the returned result, especially since this is hit by `/artifacts/{id}/review`.
- LOW — `review_artifact()`'s status `"completed_fallback"` is documented but the literal `outputs={intent: fallback_dict}` keys it on the *intent* string (`"review"` / `"analyze"`). All other graph-produced outputs key by `output_key` like `"code_review"`. Slight UI confusion possible if consumers branch on output keys.
- LOW — Line 309: `result.errors` from the LLM path is leaked into the fallback-result `errors` list. That's fine, but if a future caller surfaces those errors verbatim, the user sees "transport failed" alongside fallback findings without clear framing.
- LOW — `correlation_id` defaults to `workflow_run_id` (line 115). For Temporal runs this is the *pre-allocation* UUID, not Temporal's own run_id — fine but worth knowing when correlating with Temporal's UI.

### 2.3 `agents/bmad/__init__.py`

Re-exports only `build_bmad_graph` + `run_bmad_graph`. Clean.

### 2.4 `agents/bmad/state.py`

`BMADWorkflowState` is `TypedDict, total=False`. Useful — graph nodes can return partial states without satisfying every key. LOW — the type is purely structural; LangGraph won't actually validate it. Acceptable.

### 2.5 `agents/bmad/graph.py`

- LOW — `_compiled_graph` is module-level cached (line 51). In a forking server (uvicorn workers, pytest-xdist) each process gets its own cache. Fine. But `build_bmad_graph(force_rebuild=True)` is the only way to invalidate, and `clear_cache()` in `bmad_loader.py` doesn't reset this — minor footgun if you hot-swap node functions in dev.
- LOW — `run_bmad_graph(...)` accepts `organization_id` and `requirement_text` as optional, then never validates that the project_id/requirement_id non-empty. `HelixBMAD.__init__` does — but anyone calling `run_bmad_graph` directly bypasses that. Add a guard or document the contract.
- LOW — Final-status computation (lines 174–183) is sequential `if/elif`; the "running" fallback path is the catch-all. If `errors` is set AND `approval_decision == "approved"`, the run reports `failed`, masking that the planning chain partially completed. This is probably right but should be documented as "errors take priority over decision".
- LOW — `_build_final_output` constructs a `BMADFinalOutput` and immediately `model_dump()`s it. Skipping the model would save a Pydantic validation pass per run; keep it for now as the validation surfaces schema drift.

### 2.6 `agents/bmad/nodes.py`

- LOW — Every node has identical boilerplate: call `_run(...)`, no per-node specialisation. Worth folding into a node factory `make_node(output_key, agent_code, skill_name, model, upstream, filename)`. Pure refactor — no behaviour change.
- LOW — `_apply_result` sets `status="running"` unconditionally even for the *last* implementation node (paige_docs). The final `status="completed"` only emerges from `run_bmad_graph`'s post-processing (line 178 of graph.py). Works, but it means while LangGraph is mid-flight the status field is stale. Acceptable for a sync run; not great for Temporal observers if anyone queries the graph state mid-flight (they don't — Temporal exposes its own queries).
- MED — `winston_project_context_node` uses `output_model=ArchitectOutput` (line 137). `bmad-generate-project-context` actually produces a *project context* document — a different artifact than an architecture decision record. The frontmatter fields will be largely irrelevant (source_systems, target_systems, etc.). The markdown body will still carry the context, but the parsed metadata is essentially meaningless. Worth either a dedicated `ProjectContextOutput` model or an explicit comment that the metadata is intentionally minimal here.
- LOW — `winston_stories_node` / `winston_readiness_node` also reuse `ArchitectOutput`. Similar mismatch: their primary deliverables (epics/stories list, readiness assessment) don't map cleanly onto `source_systems` etc.
- LOW — `approval_gate_node` keys its output as `"approval_gate"` in `outputs`, but `_build_final_output` expects `outputs.get("approval_gate")` — match. OK.
- LOW — Upstream-agent lists for some nodes look wrong: `winston_stories_node`'s upstream includes `"bmad-agent-architect"` (line 202), which is itself. The architecture artifact written *just* before by `winston_architecture_node` is what stories needs — but `collect_prior_context` will fetch *every* `bmad-agent-architect` artifact for this project, including the architecture doc. Works, but each Winston node's outputs accumulate so later Winston nodes get larger prior_context bundles than upstream agents do — bloat risk.
- LOW — Mary's `upstream_agents=["bmad-agent-architect"]` (line 150) is correct — she needs the project-context doc. But the *only* Winston artifact at that point is project-context; subsequent Mary re-runs in the same workflow would see no new architect data.

### 2.7 `agents/bmad/schemas.py`

- LOW — Pydantic models use `Field(default_factory=list)` for lists. `RiskItem` has all required string fields (title/impact/mitigation) — a missing field on a real LLM run will fail validation. Could move to `Field(default="")` for the string fields to be resilient. (The mock path always supplies them; the LLM path won't if the LLM forgets.)
- MED — `BMADFinalOutput` has no `project_context`, `architect_stories`, or `architect_readiness` fields, but `run_bmad_graph` writes those into `outputs` (via nodes.py). `_build_final_output` discards them silently. Tests may not notice because they introspect `outputs` directly. Worth either adding the fields or documenting why they're excluded.
- LOW — `BusinessAnalystOutput = AnalystOutput` + `ValidationPlanOutput = QAOutput` are aliases for backward compat. Fine — keep until the last consumer is migrated.
- LOW — `AGENT_OUTPUT_MODELS` mapping omits `bmad-agent-architect` → `ArchitectOutput` is present but is mapped to ONE model even though Winston has three skills with different deliverables. Mapping is "by agent code" not "by skill", which is fine for the current codebase but inadequate for future per-skill schemas.

### 2.8 `agents/runtime/__init__.py`

Long re-export list. Clean.

### 2.9 `agents/runtime/models.py`

Static model registry. Pure data; nothing to review functionally.

- LOW — Anthropic mapping `claude-opus-4-7` matches the env declaration. Anthropic's spec on the wire uses dotted form `claude-opus-4.7` on some routes; double-check your provider rows match.
- LOW — `DEFAULT_MODELS["custom"] = ""` will surface as an empty `model` passed to `CallContext`. The CustomProvider sends `"model": ""` to the upstream. Some OpenAI-compatible mirrors error on empty model; UI should reject empty model for custom providers at config time.

### 2.10 `agents/runtime/artifact_store.py`

- LOW — `_slug()` (line 86) replaces any char outside `[a-zA-Z0-9._-]` with `-`. This is the only path-traversal defence and it works: a `project_id` of `"../evil"` becomes `"evil"` (leading `-` stripped). Confirmed safe for both `project_id` and `filename`. Note: `skill` is NOT slugged when used as a directory component because skills are passed in by code, not user input. Still, defensive `_slug()` on `agent_code` would close a hypothetical future path-injection vector. Worth a one-line add.
- LOW — `_dump_frontmatter` lazily imports `yaml`. Same in `_parse_artifact`. Each import adds ~1 ms on first call; subsequent calls are cached. Fine.
- LOW — `_FRONT_RE` uses `re.DOTALL` and `re.match`. Pattern is correct. A document missing the trailing `\n---\n` (e.g., `---\nfoo: bar\n---` with no body) will fail to match, and the whole text will be returned as body. Probably fine.
- LOW — `write_artifact` uses `tempfile.mkstemp(prefix=".artifact-", dir=dir_path)`. Tempfile lives in the same dir, so `os.replace` is atomic on POSIX and Windows (NTFS). 
- LOW — Line 191: `stable.write_text(text, encoding="utf-8")` is NOT atomic. If two concurrent project-context writers race, the file can be truncated. The likelihood is low (only Phase 0 produces this artifact, and it runs once per workflow), but for safety the mirror should also tempfile+rename.
- LOW — `list_artifacts` does `sorted(sub.glob("*.md"))` — string sort is fine here because the filename prefix is `YYYYMMDDTHHMMSSZ`, which is lexicographically chronological.
- LOW — `read_latest` reads `latest.json` then opens the latest file. There's a TOCTOU between index read and file open — but each artifact's filename is timestamp-prefixed and never overwritten, so this is benign.
- LOW — `collect_prior_context` returns `list[dict]` with `body` keys populated from `read_artifact`. Body is read in full per artifact every call — no streaming. For a deep pipeline (10+ upstream artifacts each 50KB) you'd load 500KB into memory + send most of it to the LLM. The budgeter truncates downstream but you've still done the disk I/O. Acceptable.
- LOW — `planning_root_for_project` always `mkdir(parents=True, exist_ok=True)`. Idempotent but the side effect of *just calling this getter* creating directories is mildly surprising. Consider exposing a read-only variant.

### 2.11 `agents/runtime/bmad_executor.py`

This is the biggest module and the most important. Comments inline.

- HIGH — Line 355–399 (`_resolve_provider_for_org`) and `agents.runtime.llm_client.call_llm` both import `app.db.session.SessionLocal` and `app.models.llm.*`. This is the leakage of the backend into the worker: in worker context the worker is supposed to use `worker.db.session.SessionLocal` (per GAP-8 docstring). The current behaviour means the worker creates BOTH sessions and **shares the backend SQLAlchemy engine** through `app.db.session.SessionLocal`. That engine pool was sized for the backend's HTTP load. Two implications:
  1. The worker's "DB decoupling" is incomplete.
  2. Importing `app.db.session` triggers backend's settings init (Sentry/OTLP/env validation) in worker processes — exactly what `worker/db/session.py` docs say it should avoid.
- LOW — Line 354: `from app.db.session import SessionLocal` etc. import inside the function, which keeps the cold-path penalty out of module load — good. But it doesn't fix the engine-sharing issue.
- LOW — `_token_budget()` env override floor is 1000 (line 73). Sensible. `_DEFAULT_TOKEN_BUDGET = 6000` — note: 6000 tokens is conservative for 2026-era 200K+ context models. The default rules out the entire SKILL.md body for skills like `bmad-dev-story` (which is 25K+ chars). Worth bumping the default — see Section 6.
- LOW — `_estimate_tokens` rounds DOWN (`max(1, len // 4)`). 3.5 chars/token is the better rule for monospaced markdown; 4 chars is conservative (under-estimates count → over-estimates remaining budget → less aggressive truncation). Probably fine but consider `(len + 3) // 4` to round up.
- LOW — `_truncate_smart` keeps head + tail with a marker line. The reserve of 80 chars for the marker can be exceeded when `label` is long (e.g., the actual labels are 30–40 chars), and the marker line itself is `"\n\n[... ... ...]\n\n"` which is 22+label chars. The math works out but the safety margin is thin.
- MED — `_build_system_prompt` line 140: `output_model.model_fields[name].annotation` is stringified via `str(field.annotation)`. For complex types like `list[RiskItem]` this produces something like `list[agents.bmad.schemas.RiskItem]` — readable but doesn't tell the LLM what `RiskItem` *contains*. The LLM has to guess the sub-schema. Inlining each nested model's JSON schema would yield much better real-LLM output quality.
- LOW — `_parse_metadata` uses `model_validate(front)` against the YAML frontmatter dict. If frontmatter contains a string but the model expects `list[str]`, validation fails with a useful error. Good.
- MED — Line 614–622: the "real LLM output failed parse → fall back to mock" path is right intent, but the *mock fallback markdown* is then parsed AGAIN at line 623. If the mock generator itself can't satisfy the model (unlikely but possible for unusual schemas), the function returns `success=False` *with* a mock artifact — the executor proceeds to `if parsed is None` at line 625 → returns `success=False, artifact=None`. Net effect: a transient LLM parse failure causes the run to fail outright. Better behaviour would be to ALWAYS save the raw markdown (success=False, but `raw_text != ""` and `artifact is not None`) so operators can see what the LLM produced.
- LOW — `_build_mock_markdown` looks at annotation strings (`"list" in annotation`, `"bool" in annotation`, etc.) to choose defaults. Brittle but adequate; covers the actual schema types in `agents/bmad/schemas.py`.
- MED — `_try_pydantic_ai` always selects the *first* org-active provider for "bmad-agent" via `resolve_routing`. That means per-agent overrides for analyst/pm/architect/etc. are NOT honoured by the PydanticAI transport — only by the httpx transport (`call_llm` is per-agent). Confirmed by tracing: `_resolve_provider_for_org` passes `"bmad-agent"` literal to `resolve_routing`. Worth making this `agent_code` so per-agent mappings work for the typed-LLM path too.
- LOW — Line 384–394: provider lookup re-queries by `pid` after `resolve_routing` (line 383). If `resolve_routing` returns the SAME pid (no mapping override), this is wasted SQL. Cache the lookup or merge the two queries.
- LOW — `_try_httpx` swallows ALL exceptions from `call_llm`. Fine — `call_llm` itself is already defensive. Slight code-smell: double try/except.
- LOW — Line 482: `with timed_run(agent_code=agent_code, skill=skill_name) as metric_ctx:` — the context manager records the metric on `__exit__`. If `_execute_agent_skill_inner` raises (it shouldn't — it catches `FileNotFoundError`), the `_outcome` field stays `"unknown"` and `record_run` records `outcome="unknown"`. Marginal observability gap.
- LOW — `correlation_id` is propagated into the artifact frontmatter but NOT into Prometheus labels. Labels are bounded by cardinality — adding a UUID would explode label space. Fine to leave out; mention in docs.
- HIGH — Transport order default `("pydantic_ai", "httpx", "mock")` — `pydantic_ai` is tried first, which requires importing `pydantic_ai.Agent`. PydanticAI internally bundles its own httpx clients and may instantiate them eagerly. In a sandbox with no network egress, this can incur ~5–10s of timeout before fallback. The httpx path is faster to fail. Consider documenting the order's perf characteristics.
- MED — `_try_pydantic_ai` sets `os.environ[env_var] = api_key` (lines 78–79 in pydantic_ai_client.py) — see Section 2.13. The bmad_executor never reads or logs the env var so the key doesn't leak through THIS file, but the global env var write is a security/concurrency footgun (logged in 2.13).

### 2.12 `agents/runtime/bmad_loader.py`

- HIGH — Line 184 (`subprocess.run`) — the helper runs *Python scripts* via subprocess. Two real risks:
  1. The script path is built from `bmad_install_dir() / "scripts" / script_name`, where `script_name` is hard-coded by the caller (only `"resolve_config.py"` and `"resolve_customization.py"`), so no injection risk.
  2. `sys.executable` is used — good, no PATH-shadowing risk.
  3. `args` are passed as separate list elements — no shell, so argument injection is moot. Safe.
  4. The 15-second timeout (line 192) is generous; for a deep cold start (Python startup + tomllib load + 4-layer merge) this is fine.
- MED — `lru_cache(maxsize=1)` on `load_bmad_config` and `maxsize=32`/`128` on the agent/skill caches: these are PROCESS-level. In a long-running worker, if customize.toml changes on disk you must call `clear_cache()` — no file-watching. Acceptable but should be documented in deployment notes.
- LOW — `_find_skill_dir` does `(root / "bmm-skills").glob("[0-9]-*")`. The phase ordering depends on dir name prefix `1-`, `2-`, `3-`, `4-`. If BMAD-METHOD ever renames a phase folder, the lookup silently misses. Worth adding a fallback search over all subdirs.
- LOW — `_agent_phase` is a hard-coded heuristic dict (lines 130–138). Adding a new agent code (e.g., `bmad-agent-security`) won't be reflected here — falls through to `"Implementation"`. Document the requirement.
- MED — Line 316: `root.glob(raw.removeprefix(str(root)).lstrip("/\\"))` — handles persistent_facts glob expansion. If a glob entry references a path *outside* the project root (an attacker-controlled customize.toml), the glob silently misses (rather than escaping the sandbox). Good defence by construction. But the `if "*" in raw` branch ONLY globs when an asterisk is present; for non-glob entries it builds `Path(raw)` and checks `is_file()` — that path is NOT restricted to `root`. A malicious customize.toml could surface `/etc/passwd` as a persistent fact (file would be read by `build_persona_prompt` and embedded in the LLM prompt). Defence: verify `path.is_relative_to(root)` before adding.
- LOW — Line 322: `agent_block.get("name", agent_code)` — falls back to the agent code if no `name` is set. Fine.
- LOW — `_run_bmad_script` reads stdout with `encoding="utf-8", errors="replace"`. Bad bytes become `U+FFFD` and might break the JSON parse silently. The next `json.loads` will raise and the function returns `{}`. Acceptable.
- LOW — Line 211: `if result.returncode != 0: ... return {}` — the fallback then falls through to the in-process `tomllib` merge. Good defensive design. But there's no metric for "subprocess fell back to in-process merge" — operators can't see this happen.
- LOW — Persistent-fact globs (line 316): If `root.glob(...)` returns a long list, every fact gets read into memory by `build_persona_prompt` via SKILL.md. Pre-check fact list length in `load_bmad_agent` and warn at >50 entries.

### 2.13 `agents/runtime/llm_client.py`

- HIGH — Line 26: `from app.db.session import SessionLocal` — same backend coupling as `bmad_executor._resolve_provider_for_org`. See Section 3.
- LOW — `LLMProvider.status == "active"` — works but if multiple active providers exist for one org, `.first()` is non-deterministic ordering. Add `.order_by(LLMProvider.created_at.desc())` or similar.
- LOW — Line 46: `int(max_tokens)` — `resolve_routing` returns 4096 as default; if a provider record has `max_tokens=None` and no mapping override, the route would crash with `int(None)`. Confirmed in router source (`resolve_routing` returns the literal `4096` in the default branch). OK.
- LOW — Exception catch is `except Exception` then logs at WARNING — fine, but the same pattern is repeated in every adapter via `safe_call`. Double-logged on failure.
- LOW — `decrypt_value(secret.encrypted_api_key)` — backend-side decryption is invoked from the worker. As long as `HELIX_SECRET_KEY` env var matches between backend and worker, OK. Worth a deployment-time check.
- LOW — No retry. If the upstream times out once, the call fails and the executor falls through to mock. The provider adapters return `None` on non-2xx — no retry-on-429, no exponential backoff. See Section 6.

### 2.14 `agents/runtime/metrics.py`

- LOW — Counters/Histograms are module-level globals. Multi-import in pytest (per worker) will work because `prometheus_client` handles redefinition gracefully (`Counter` raises ValueError on duplicate; but the wrapper script's `import` is once-only).
- LOW — `record_run` swallows all exceptions at DEBUG level — perfect.
- LOW — `timed_run` uses `time.monotonic()` — correct for elapsed time.
- LOW — `prompt_tokens` histogram buckets cap at 50K. Larger prompts get clamped into the `+Inf` bucket and lose granularity. Tune buckets when you know your real prompt-size distribution.

### 2.15 `agents/runtime/pydantic_ai_client.py`

- HIGH — Lines 76–101: the function writes the API key into `os.environ[env_var]` and then restores it in a `finally:`. **This is not thread-safe.** Two BMAD agent runs concurrent in the same process (Temporal sync activities executed in a thread pool, which is the default) WILL race on the env var. Worst case: agent A's call leaks agent B's API key when B's restoration runs first. PydanticAI's `Agent(...)` constructor reads env vars at instantiation, so a brief window of env-var pollution is unavoidable with this approach. The fix is to use PydanticAI's explicit `Provider` API (e.g., `OpenAIProvider(api_key=...)`) — supported since pydantic-ai 0.0.13. The current locked version is 1.102 — definitely supported.
- HIGH — Same code path: if PydanticAI internally LOGS the env var (some debug paths echo init args), the API key surfaces in worker logs. Mitigation: switch to explicit provider construction.
- LOW — `_PROVIDER_PREFIXES` maps `"deepseek"` → `"openai:"` — yes, DeepSeek is OpenAI-compatible, but PydanticAI's `openai:` provider hits `api.openai.com` by default. The `base_url` is not actually wired through here — line 80 just passes `model_id` to `Agent(...)` with no `provider=` override. **This means the PydanticAI transport will always call OpenAI for DeepSeek/OpenRouter/Custom/Local providers.** A genuine bug that silently breaks the typed-LLM path for non-OpenAI OpenAI-compatible providers.
- LOW — `getattr(run, "data", None) or getattr(run, "output", None)` — defensive in case the PydanticAI API rename happens. Worth pinning the version in requirements.
- LOW — `is_available()` re-imports `pydantic_ai` on every call. Cheap (cached by Python), but you could memoise the boolean.

### 2.16 `agents/runtime/static_analysis.py`

- LOW — Stdlib-only — confirmed.
- LOW — `_SECRET_PATTERNS` covers AWS access keys, OpenAI keys, Slack tokens, PEM private keys. Missing: Anthropic keys (`sk-ant-...`), Google API keys (`AIza...`), GitHub tokens (`ghp_*`/`gho_*`), Stripe (`sk_live_`/`sk_test_`), Twilio (`AC`/`SK`). Worth expanding.
- LOW — `_GENERIC_SECRET_ASSIGN` regex requires hex-only RHS (lines 61–66). Most modern API keys are alphanumeric (e.g., `Bearer abcd1234...`); the hex constraint is too tight. Consider broadening to `[A-Za-z0-9_-]{32,}`.
- LOW — Cyclomatic complexity heuristic (lines 328–345): counts decision points but double-counts nested functions (line 339 explicitly accepts this). For most code this overestimates by 1–2 — fine.
- LOW — `_max_nesting_depth` only counts ast.If/For/While/Try/With as nesting. `ast.Match` (3.10+ pattern matching) is missing — modern code with match statements isn't flagged. Add `ast.Match`.
- LOW — `_function_body_length` returns line span — comment-only lines and blank lines count. A 100-line docstring would trigger the warning. Probably fine for the use case.
- LOW — `_check_assign_secret` only matches single-target assigns whose RHS is a Constant string. Doesn't catch `_x = _y = "secret"` (multiple targets) or f-strings. Worth a comment in the limitations doc.
- LOW — `_check_string_secret` (line 306) walks every string literal — pos 308 checks `if not isinstance(text, str)` after also entering on `isinstance(node.value, str)` — redundant.
- LOW — `_looks_python` line 448: the slash logic `rsplit("/", 1)[-1].rsplit("\\", 1)[-1]` handles mixed separators. Reasonable.
- LOW — `_scan_comments` uses `tokenize.generate_tokens(io.StringIO(source).readline)`. Tokenizer can raise `tokenize.TokenizeError` *or* `IndentationError` (caught). For other exception types from corrupt sources (like `SyntaxError` mid-token), the function would propagate the error. Add a broader catch.
- LOW — Non-Python sources: only line-based regex secret scan. JSON/TOML/YAML configs with multi-line secrets (PEM blocks) won't be caught because the PEM pattern requires its line to contain `-----BEGIN PRIVATE KEY-----`. Actually it does line-by-line — so a single-line PEM marker IS caught. But if the marker is split across lines, miss.
- LOW — Result schema includes a `stats` dict (line 517) that isn't in the `CodeReviewOutput` Pydantic model — confirmed `extra="ignore"` will drop it but the docstring should mention it survives in `to_dict()` callers.

### 2.17 `agents/runtime/structured_output.py`

Tiny module, all 3 patterns regex-greedy. Notes:

- LOW — `_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)` is greedy. A response containing `"foo": {"a": 1}, "bar": {"b": 2}` will match the outermost `{...}` correctly — good. But a response like `text\n{"a":1}\nmore text\n{"b":2}` will match from the first `{` to the last `}`, capturing the prose between them. The downstream `json.loads` will then fail, and the caller falls back to `{"summary": content}`. Acceptable degradation.
- LOW — `_FENCED_JSON_RE` accepts both ```json and ``` blocks. Doesn't handle `~~~` fences (less common). Fine.
- LOW — No handling of single-quoted JSON or Python-dict syntax. Strict JSON only. Right call.

### 2.18 `agents/runtime/providers/__init__.py` + `base.py`

- LOW — Self-registration at import time (`__init__.py` lines 30–42). Order is irrelevant because the registry is a dict. Fine.
- LOW — `BaseProvider.call` raises `NotImplementedError`; all subclasses implement. Good.
- LOW — `CallContext` is a `@dataclass`. No `__post_init__` validation — bad URLs/timeouts pass silently. Add basic validation if you ever expose this to user input.
- LOW — `parse_text_to_dict` always returns a dict; on JSON-parse failure it returns `{"summary": content}`. This is the source of the schema mismatch when a real LLM returns prose only — the BMAD executor then re-validates the dict against the Pydantic schema and gets `summary=<huge prose>` with empty lists for everything else. Worth flagging in logs when this fallback fires.
- LOW — `safe_call` catches `Exception` (not `BaseException`). Right.

### 2.19 `agents/runtime/providers/openai_provider.py`

OpenAI Chat Completions. Wire format is correct:

- URL: `POST /v1/chat/completions` — matches OpenAI's published spec.
- Auth: `Authorization: Bearer <key>` — correct.
- Body: `{"model", "temperature", "max_tokens", "messages": [system, user]}` — correct.
- Response: `resp.json()["choices"][0]["message"]["content"]` — correct.

- MED — No `max_completion_tokens` (the newer field GPT-5 reasoning models require). On GPT-5.5-thinking the request may fail or silently truncate. Worth detecting model id + switching field.
- MED — No `seed` param exposed — reproducible runs would be welcome for the BMAD planning phase.
- LOW — No retry on 429 / 5xx. OpenAI publishes `Retry-After` headers. Adding a `httpx.HTTPTransport(retries=2)` or a small `tenacity` wrapper is cheap.
- LOW — No streaming. Synchronous one-shot. Fine for the BMAD use case.
- LOW — On non-2xx, `_call` returns `None` — but doesn't log the status code or response body. Operators debugging a 401 vs 429 vs 500 have nothing in the worker log. Add `logger.warning("openai status=%s body=%s", resp.status_code, resp.text[:500])`.
- LOW — Token-security: `ctx.api_key` only appears in the `Authorization` header. No logging of the header. Good.
- LOW — `resp.json()["choices"][0]["message"]["content"]` will raise `KeyError`/`IndexError` if OpenAI returns an empty `choices` array (rare — happens on certain `tool_choice` configs). `safe_call` catches; you lose the body. See above.

### 2.20 `agents/runtime/providers/anthropic_provider.py`

Anthropic Messages API. Verified against `docs.anthropic.com`:

- URL: `POST /v1/messages` — correct.
- Headers: `x-api-key`, `anthropic-version: 2023-06-01`, `content-type: application/json` — correct.
- Body: `{"model", "max_tokens", "system", "messages": [{role:user, content:...}]}` — correct.
- Response: `resp.json()["content"][0]["text"]` — correct.

- MED — `anthropic-version: 2023-06-01` is the original Messages API version. As of 2026 there are newer optional versions; 2023-06-01 is still the stable baseline and will continue working, but you may miss features like extended thinking. The newest API version `2026-02-15` is what the SDK uses; consider bumping after testing.
- MED — No `temperature` in the body. Anthropic supports `temperature` (0..1) and defaults to 1.0 — that's hotter than Helix probably wants. Add `temperature=ctx.temperature`.
- MED — Claude Opus 4.7 supports **extended thinking**. To use it you'd need to send `thinking: {type: "enabled", budget_tokens: 16000}`. Not used; not necessarily a bug but you're leaving Opus's headline feature on the table.
- LOW — No retry on 429. Anthropic returns `retry-after` on rate-limit; same comment as OpenAI.
- LOW — On streaming responses or tool_use blocks, `content[0]["text"]` may not be the text block — first content block could be a `tool_use`. For BMAD we don't use tools, but if anyone enables them, this would break.
- LOW — No `top_p` / `stop_sequences` exposed.

### 2.21 `agents/runtime/providers/gemini_provider.py`

Google Gemini direct API (`generativelanguage.googleapis.com`). Verified:

- URL: `/v1beta/models/{model}:generateContent?key={api_key}` — correct (current Gemini API form).
- Body: `{"contents": [{"parts": [{"text": ...}]}], "generationConfig": {"temperature", "maxOutputTokens"}}` — correct.
- Response: `resp.json()["candidates"][0]["content"]["parts"][0]["text"]` — correct.

- HIGH — **The API key is in the URL query string.** Gemini accepts both `?key=` and `x-goog-api-key:` header. URL placement means the key WILL appear in:
  - httpx debug logs (if `HTTPX_LOG_LEVEL=debug`)
  - any reverse proxy access logs in the path
  - any opentelemetry HTTP spans (the URL is the span name)
  - exception messages (`httpx.HTTPStatusError` includes the URL)

  Move to `headers={"x-goog-api-key": ctx.api_key}` instead. The opentelemetry-instrumentation-httpx package is in `requirements.lock` — meaning Gemini calls' URLs (with the key) are being exported as OTLP spans by default. **This is a real key-leak vector.**
- MED — The `v1beta` path. Gemini 3 models are stable on `v1` for some — verify with current docs. `v1beta` still works but may rate-limit differently.
- MED — System prompt concatenation `f"{ctx.system_prompt}\n\n{ctx.user_prompt}"` — Gemini supports a top-level `systemInstruction` field (since Gemini 1.5). Using it would let the model treat the system prompt more authoritatively and would also save those characters from counting against `maxOutputTokens` indirectly. Worth migrating.
- LOW — No safety setting passed (`safetySettings`). Default safety filters may block legitimate migration content (e.g., "kill" a process). Consider passing relaxed `BLOCK_NONE` thresholds for migration content with an admin warning.
- LOW — Response path doesn't handle `promptFeedback.blockReason` — when the model blocks, `candidates` may be empty, raising IndexError → safe_call catches → None. Log the block reason.

### 2.22 `agents/runtime/providers/deepseek_provider.py`

DeepSeek (OpenAI-compatible).

- LOW — Legacy alias map (`deepseek-chat` → `deepseek-v4-flash`). This is provider-side too — the legacy IDs are still accepted by DeepSeek's API. Mapping client-side is defensive but redundant; if DeepSeek ever changes the mapping it'll already be reflected on their side. Fine to keep as documentation.
- Wire format identical to OpenAI: correct.
- LOW — Same logging/retry gaps as OpenAI.
- LOW — DeepSeek-Reasoner (V4 Pro) returns `reasoning_content` in addition to `content`. Current code only reads `content`. For QA/review skills you might want the reasoning trace. Optional.

### 2.23 `agents/runtime/providers/openrouter_provider.py`

OpenRouter — OpenAI-compatible router.

- LOW — Adds `HTTP-Referer` + `X-Title` headers for attribution — OpenRouter does honour these for billing/analytics. Correct.
- LOW — Default `base_url = https://openrouter.ai/api/v1`. Correct.
- Wire format correct.
- LOW — No `route` parameter (`fallbacks`, `provider.order`). OpenRouter supports these — would let you set hard fallbacks. Optional.

### 2.24 `agents/runtime/providers/bedrock_provider.py`

Largest provider file. Routes by model ID prefix. Verified families:

- `anthropic.*` — body matches Bedrock's Claude wrapper (`anthropic_version: "bedrock-2023-05-31"`, `system`, `messages`). ✅
- `meta.*` — Llama prompt with `<s>[INST]...[/INST]` markers, `max_gen_len`, `temperature`. ✅ (Llama 4 still uses this template on Bedrock.)
- `mistral.*` — Mistral uses `<s>[INST]...[/INST]` too — `_build_body` collapses both branches but switches the max-tokens field name via Python expression `"max_gen_len" if mid.startswith("meta.") else "max_tokens": ctx.max_tokens` — **this is a parser-aware key trick**. Confirmed legal: the dict literal evaluates the key expression first. Correctness OK; readability poor — extract a small `if`.
- `cohere.*` — flat `prompt`. ✅ (matches Bedrock's Cohere Command R+ schema).
- `amazon.*` (Titan) — `inputText` + `textGenerationConfig.temperature/maxTokenCount`. ✅
- `deepseek.*` / `openai.*` — OpenAI-shaped `messages`. ✅ (Bedrock 2026 additions.)
- Unknown families — best-effort OpenAI-shaped pass-through. ✅

Extraction (`_extract_text`):

- `anthropic.*` — `raw["content"][0]["text"]` ✅
- `meta.*` — `raw["generation"]` ✅
- `mistral.*` — `raw["outputs"][0]["text"]` ✅
- `cohere.*` — `raw["generations"][0]["text"]` ✅
- `amazon.*` — `raw["results"][0]["outputText"]` ✅
- `deepseek.*` / `openai.*` — `raw["choices"][0]["message"]["content"]` ✅

Issues:

- HIGH — Lines 57–61: AWS creds passed via `extra_config` are read as `aws_access_key_id` / `aws_secret_access_key`. **The `LLMProvider` table stores `api_key` separately from `extra_config`** — `bedrock_provider` ignores `ctx.api_key` (correctly noted in docstring). But the secret_service decrypts ONLY `secret.encrypted_api_key`. AWS secret access keys would have to be stored elsewhere — likely in `extra_config` plaintext. The audit needs to check whether `extra_config` gets encrypted; the current shape suggests it doesn't. **If `extra_config` is unencrypted, AWS secret access keys sit in plain text in the LLMProvider table.**
- MED — `boto3.client("bedrock-runtime", **client_kwargs)` is created per-call. No connection pooling. boto3 sessions are cheap-but-not-free. Cache `boto3.Session` per (region, creds) tuple to reduce per-call overhead by ~20–50ms.
- MED — `client.invoke_model(...)` is synchronous-only. There's `invoke_model_with_response_stream` for streaming — fine to leave alone.
- LOW — `max_tokens` is the same value passed regardless of family. Llama 4 caps at much lower than Claude. Add a per-family max.
- LOW — `temperature` is missing from the `anthropic.*` body (line 82–87) — Bedrock's Claude wrapper supports `temperature`. Default of 1.0 will be used. Same issue as direct Anthropic adapter.
- LOW — On a Bedrock 4xx response, `client.invoke_model` raises `botocore.exceptions.ClientError`. `safe_call` catches and logs — but doesn't surface the AWS error code (e.g., `ThrottlingException` vs `AccessDeniedException`). Worth a targeted log.

### 2.25 `agents/runtime/providers/vertex_provider.py`

Google Vertex AI via the `vertexai` SDK.

- LOW — Requires `gcp_project` in `extra_config`; returns None with a warning if missing. Fine.
- LOW — `vertexai.init(project=..., location=...)` mutates GLOBAL SDK state. Two concurrent calls with different `gcp_project` will race. Acceptable if one Helix instance serves one GCP project; document.
- LOW — `system_prompt` is concatenated into the user text. Vertex's Gemini supports `system_instruction` since SDK 1.40+. Worth upgrading.
- LOW — `model.generate_content(full_prompt, generation_config=...)` — no `safety_settings`. Same comment as Gemini direct.
- LOW — No streaming, no tools — fine for BMAD.
- LOW — `getattr(response, "text", "")` — Vertex's SDK exposes `.text` as a property; if the response is multipart or has no text, returns "". Defensive enough.
- LOW — Doesn't handle quota errors specifically.
- LOW — No retry / backoff.

### 2.26 `agents/runtime/providers/azure_provider.py`

Azure OpenAI via the `openai.AzureOpenAI` SDK.

- LOW — Requires `azure_endpoint` + `deployment_name`; returns None if missing. ✅
- LOW — `api_version` defaults to `"2026-01-01"` — verify against your Azure OpenAI tenant; deployments may pin to earlier versions.
- LOW — `model=deployment` (line 57) — Azure routes by deployment name; the SDK requires this. Correct.
- LOW — `client = AzureOpenAI(...)` per call — Azure client is light but does TCP setup; consider pooling.
- LOW — `response.choices[0].message.content` — SDK response object; OK.
- LOW — Doesn't surface `response.choices[0].finish_reason` — content_filter blocks would silently return empty string.
- LOW — `timeout=ctx.timeout` is passed at the request level — supported by the SDK.

### 2.27 `agents/runtime/providers/custom_provider.py`

OpenAI-compatible catch-all.

- LOW — Returns `None` immediately if `base_url` is missing. ✅
- LOW — Empty-API-key path: `headers={}` if no api_key (line 33). Some endpoints (Together, Groq) still require a header even with placeholder; documentation should warn.
- LOW — Wire format identical to OpenAI. ✅
- LOW — Same logging gaps as OpenAI.

### 2.28 `agents/runtime/providers/local_provider.py`

Ollama default.

- LOW — Defaults `base_url` to Ollama's `http://localhost:11434/v1`. Note that Ollama's OpenAI-compatible mirror is at `/v1` — correct.
- LOW — `Authorization: Bearer {api_key or 'local'}` — Ollama ignores the header. Fine.
- LOW — Same wire format as OpenAI.
- LOW — No retry. Local model first-token latency can be high; default `timeout=60s` may be tight for large models on CPU.

### 2.29 Tests

**`conftest.py`**

- LOW — Copies the entire `_bmad/` directory into a tmp dir per test (`shutil.copytree`). On Windows this is slow per test. For a test session that runs all 9 files, this is 9× setup overhead. Worth scoping `isolated_artifact_root` to `module` if BMAD configs are read-only inside the test. (Cache invalidation via `clear_cache()` makes module scope safe.)
- LOW — `sys.path.insert(0, str(_REPO_ROOT))` is unhygienic — modifies global path. Acceptable for the test harness.
- LOW — Sets `BMAD_METHOD_ROOT` to the real read-only tree — correct.

**`test_artifact_store.py`**

- LOW — `test_latest_index_resolves_most_recent` uses `time.sleep(1)` to force a different timestamp. Wall-clock-dependent. Could use `monkeypatch` on `datetime.now`. Works; slightly flaky on overloaded CI.

**`test_bmad_executor.py`** — adequate. Covers mock-path success + prior-context handoff.

**`test_bmad_loader.py`**

- LOW — `test_load_bmad_skill_product_brief` asserts `skill.phase == "1-analysis"`. This depends on BMAD-METHOD's directory layout — if upstream BMAD renames phases, test breaks. Worth pinning a BMAD-METHOD version.

**`test_graph.py`** — strong end-to-end coverage of pending/approved/rejected paths.

**`test_helix_class.py`** — covers HelixBMAD facade, including the stable project-context.md mirror.

**`test_observability.py`** — covers correlation_id propagation and metrics smoke.

- LOW — Doesn't assert that Prometheus counter values increment — only that `labels(...)` returns a child. Stronger assertion would call `child._value.get()` (private API but commonly used in tests).

**`test_prompt_budget.py`** — solid. Tests truncate-smart, env override, budget allocation, and end-to-end token-budget metadata in frontmatter.

**`test_static_analysis.py`** — comprehensive coverage of complexity, nesting, long-func, missing-docstring, secrets, broad-except, eval/exec, TODO, syntax-error, non-Python files.

### 2.30 Worker

**`worker/main.py`**

- LOW — `APP_ENV` check (line 56–63) — production exits non-zero, dev exits 0. Reasonable. But Compose's `restart: unless-stopped` will restart on non-zero exit, which is what production needs.
- LOW — `Worker(client, task_queue, workflows=[...], activities=[...])` does not set `max_concurrent_activities` — defaults to 100. For 13 sync activities each making an LLM call, that's a lot of httpx in flight per worker process. Worth tuning down.
- LOW — `Worker` is started by `await worker.run()` which blocks until shutdown. No SIGTERM handling — Temporal SDK handles signals internally. Confirmed OK.
- LOW — `logging.basicConfig(...)` only runs on `__main__` — fine.
- LOW — No graceful drain timeout configured; activities killed mid-flight will be retried by Temporal on next worker boot.

**`worker/activities/__init__.py`** — empty.

**`worker/activities/bmad_activities.py`**

- LOW — `@activity.defn` on a sync `def` — Temporal runs in thread pool. Correct.
- LOW — `activity.heartbeat("bmad_graph_completed")` is called AFTER the work completes (line 49) — heartbeat after the fact is purely diagnostic. For long-running activities you'd want periodic heartbeats during execution; current code never heartbeats mid-run. The activity has a 10-minute start_to_close timeout (set in the workflow) and no heartbeat_timeout, so this is acceptable but means a stuck activity won't be detected as zombie until the start_to_close window expires.
- LOW — Re-raises on Exception. Temporal will then retry per the workflow's retry policy. ✅

**`worker/activities/bmad_node_activities.py`**

- LOW — `_execute` does `getattr(bmad_schemas, output_model_name)` (line 48) — string-based lookup. Works because `output_model_name` is a hard-coded literal in each activity. Slightly weaker type safety than passing the class directly, but Temporal needs JSON-serializable args + the class can't be JSON-serialised — so this is the right pattern. Fine.
- LOW — `_safe_heartbeat` wraps `activity.heartbeat` in a try/except for RuntimeError. Necessary when an activity function is called directly in unit tests (no Temporal context). ✅
- LOW — Every activity heartbeats twice (start + completion). No mid-run heartbeats. Same comment as monolithic activity — acceptable given the 10-minute start_to_close. If a single LLM call hangs (e.g., httpx 60s timeout × 3 retries) you'd hit 3+ minutes between heartbeats; still under timeout.
- MED — `persist_workflow_step_activity` (lines 302–329):
  - Opens `worker.db.session.SessionLocal()` — correct, worker-local session. ✅
  - Imports `app.models.workflow.WorkflowStep` — backend model class; OK because both processes use the same schema.
  - `raw_output=json.dumps({**parsed, "artifact_path": ...})` — combines `parsed` dict with artifact_path. If `parsed` already has an `artifact_path` key, this overwrites it. Low likelihood but easy to clarify.
  - `parsed_output_json=parsed` — assumes the column is a `JSONB` (it should be for performance). If parsed is None, this stores `null` JSONB — fine.
  - No `try/except` around `db.commit()` — if the DB is down, the exception propagates → activity fails → workflow retries. Acceptable for short-term outage.
  - No idempotency key. If the workflow retries the persist activity (3 attempts per `_RETRY`), you can write the SAME step 3 times. Add a uniqueness constraint or use upsert on `(workflow_run_id, step_order)`.

**`worker/workflows/__init__.py`** — empty.

**`worker/workflows/bmad_planning_workflow.py`**

- LOW — `with workflow.unsafe.imports_passed_through()` — correct usage to skip sandbox validation for `httpx`/`yaml`/`subprocess` deps inside the activity module.
- LOW — Determinism: no `datetime.now`, `random`, `time.time`, or external I/O in workflow body. ✅
- LOW — `start_to_close_timeout=10 minutes` for ALL 13 BMAD nodes in one activity is tight if upstream LLMs are slow. With 3 retries × 10 minutes = 30 minutes worst case. Document the SLA.
- LOW — Retry policy maximum_attempts=3 — combined with provider adapters' lack of retry-on-429, this provides some resilience. Fine.

**`worker/workflows/bmad_per_node_workflow.py`**

- LOW — All 13 activities use the same `_RETRY` and `_ACTIVITY_TIMEOUT`. Persistence uses a separate `_PERSIST_TIMEOUT` of 30s — sensible.
- LOW — Approval timeout is 48 hours (`_APPROVAL_TIMEOUT`). If the human never approves, the workflow ends with status `pending` (Temporal raises `WorkflowTimeoutError` actually — wait, no: `workflow.wait_condition(..., timeout=...)` raises `TimeoutError` after the duration). The current code doesn't catch this — the workflow will exit with WorkflowFailed status. May not be what the UI expects. Wrap with try/except for `asyncio.TimeoutError` (Temporal's wait_condition raises it) and return a clean "expired" status.
- LOW — `self._outputs["project_context"] = (await run_step(...))["parsed"]` — if `parsed` is `None` (the activity failed), `outputs["project_context"] = None`. Downstream code may not expect None. Acceptable: activity failure with maximum_attempts=3 will already have exhausted retries and Temporal will fail the workflow.
- LOW — `self._artifact_paths` is mutated inside `run_step` (line 132). Determinism still holds because the mutations are derived from activity return values. ✅
- LOW — Queries (`current_step`, `outputs`, `artifact_paths`) return the current in-flight state. Be aware these are point-in-time snapshots over Temporal RPC.
- LOW — No way to ABORT a workflow externally other than `terminate`. Could add a `cancel` signal for graceful abort. Optional.

**`worker/db/session.py`**

- LOW — `pool_size=3, max_overflow=2` — appropriate for a worker with 1–5 concurrent BMAD activities.
- LOW — `pool_pre_ping=True` — protects against stale connections after a Postgres restart. ✅
- LOW — Uses a global `_engine`; tests that spawn multiple processes via pytest-xdist will each have their own engine. ✅
- LOW — `_DATABASE_URL` default `postgresql://helix:helix@postgres:5432/helix` — default creds. In prod, override via env. The default should NEVER make it to prod; the loader's `pool_pre_ping` would still attempt to connect against this URL if env was missing. Fine in dev.

**`worker/Dockerfile`**

- LOW — Multi-stage build, non-root user (`uid=1000`), `pool_pre_ping=True` — good baseline.
- LOW — `PYTHONPATH=/install/lib/python3.11/site-packages:/app:/app/backend` — exposing `/app/backend` means worker imports of `app.*` use the backend code copied into `/app/backend`. Confirmed.
- MED — Healthcheck (`HEALTHCHECK`) attempts `Client.connect` to Temporal every 30s. Each connect is full gRPC — modest cost but additive. More importantly, the healthcheck **passes silently even if the worker process is dead** because `python -c` opens a fresh process. The check confirms Temporal reachability, not worker liveness. Replace with a worker-specific signal (the worker could write a heartbeat file, or expose a tiny health endpoint).
- LOW — `BMAD_METHOD_ROOT=/app/agents/bmad/BMAD-METHOD` — the vendored tree is copied via `COPY agents/ ./agents/`. Correct.
- LOW — `apt-get install` is absent — relies on `python:3.11-slim` having enough libs. `psycopg2-binary` ships its own libpq; should work. If you ever switch to `psycopg2` (non-binary), you need libpq-dev.
- LOW — `pip install --prefix=/install` is reproducible because `requirements.lock` exists. Builder doesn't COPY the source, only the requirements files — good (cache-friendly).
- LOW — Final image is python:3.11-slim — ~150 MB before deps. Fine.

**`worker/requirements.txt`**

- LOW — Top-level deps are reasonable. Versions are loose (`>=`); `requirements.lock` pins exact versions, used by Dockerfile.
- LOW — `openai`, `boto3`, `google-cloud-aiplatform` are top-level — every worker image ships with all three. Fine for OSS distribution. Could split into `requirements-bedrock.txt` / `requirements-vertex.txt` for slimmer images. Optional.
- LOW — `pydantic-ai>=0.0.13` lower bound is from 2024. Current lock is 1.102.0 (huge gap). Bump the floor for clarity.
- LOW — No version-pin on `langgraph` — `>=0.2.0` but lock has 1.2.1. Bump the floor.

**`worker/requirements.lock`** — autogenerated by pip-compile. Reproducible.

- LOW — `cryptography==48.0.0` — the floor is `>=42.0.0`. Fine.
- LOW — `httpx==0.28.1` — recent.
- LOW — `prometheus-client==0.25.0` — good.
- LOW — `openai==2.38.0` — major version of the OpenAI SDK; verify your code's compatibility with v2 (the chat completions API is stable).
- LOW — `google-cloud-aiplatform` is NOT in the lock file. The lock shows `google-genai==2.6.0` (pulled in by pydantic-ai) — but the dedicated `google-cloud-aiplatform` listed in requirements.txt isn't here. Likely missing or replaced. Check the lock regeneration pipeline.

### 2.31 `_bmad/scripts/resolve_config.py` + `resolve_customization.py`

Both files are well-documented shim wrappers that read the 3-/4-layer TOML stack and emit merged JSON.

- LOW — Both scripts exit code 3 on Python <3.11 (`tomllib` missing). Helix mandates 3.11 anyway. Documented in the shebang.
- LOW — `deep_merge` rules are identical between the two files — could be deduplicated into a shared `_merge.py`. Minor refactor.
- LOW — `_detect_keyed_merge_field` (lines 71–77 in resolve_config.py) — looks for `code` or `id` shared across ALL items in BOTH base + override. Documented behaviour. ✅
- LOW — `load_toml(..., required=True)` exits with code 1 on missing required file — only `_bmad/config.toml` is required.
- LOW — `find_project_root` in resolve_customization.py (lines 56–64) walks up until it finds `_bmad/` or `.git`. Falls back to `Path.cwd()` if not found. Comment at line 204 explains the precedence (skill-relative first, then cwd) — correct ordering.
- LOW — Both scripts print JSON via `sys.stdout.write(...)` with `ensure_ascii=False`. The caller (`_run_bmad_script`) sets `encoding="utf-8"` and `PYTHONIOENCODING=utf-8` in the env — matches. Good.
- LOW — No tests for the merge logic in the Helix test suite — relies on upstream BMAD tests. Worth adding 2–3 sanity cases.

---

## 3. Cross-cutting findings

### 3.1 Mock fallback path consistency across nodes

- All 13 nodes go through `execute_agent_skill` → `_build_mock_markdown`. The mock builder generates a frontmatter dict by inspecting `output_model.model_fields` and picking defaults by annotation substring. This is mostly consistent BUT:
  - Fields like `summary` always get a stock string, but only when named `summary`. A future model with `description` instead would get the empty-string default and fail the model_validate if that field is required.
  - `RiskItem` is never instantiated in mock mode — `risks: list[RiskItem]` becomes `[]` because `_build_mock_markdown` sees `"list" in annotation` and sets `[]`. Good — avoids `RiskItem` validation pain.
  - `ApprovalGateOutput.approval_required` always defaults to `True` in mock mode, regardless of whether the user already supplied `approval_decision`. The actual approval_gate_node never goes through `execute_agent_skill` (it's a pure state transition in nodes.py:225), so this is a no-op in practice. But the existence of these special-cases in `_build_mock_markdown` for fields that never reach it is dead code.
  - In Temporal worker context, `approval_gate` is NOT a node — it's the `wait_condition` in the workflow. So the `_build_mock_markdown` approval-gate special cases would only fire for adhoc-review flows where someone runs the gate via execute_agent_skill, which doesn't happen.

### 3.2 Org-scope propagation: activity → executor → llm_client

```
HelixBMAD(organization_id=X)
  → start_temporal()  → BMADPerNodeWorkflow(input_data["organization_id"]=X)
                       → activity(input_data) → _execute(..., input_data)
                                              → execute_agent_skill(..., org_id=X)
                                                → _try_pydantic_ai(..., org_id=X)
                                                  → _resolve_provider_for_org(X)
                                                → _try_httpx(..., org_id=X)
                                                  → call_llm(..., org_id=X)
```

Tracing confirms `organization_id` flows end-to-end via the `input_data` dict and the `org_id` kwarg. ✅

- LOW — `_resolve_provider_for_org` hard-codes `resolve_routing("bmad-agent", ...)` instead of the per-agent name. See 2.11 — this means per-agent LLM mappings DON'T affect the PydanticAI path. The httpx path does pass `agent_name` correctly via `call_llm(agent_name, ...)`.

### 3.3 Correlation ID threading

```
HTTP layer (X-Request-Id) → HelixBMAD(correlation_id=Y) → _input_payload()
  → Temporal workflow input_data["correlation_id"] → activities pass via input_data
  → execute_agent_skill(correlation_id=Y) → artifact frontmatter["correlation_id"]=Y
                                          → logger.info(... corr_id=Y ...)
```

Confirmed end-to-end via `test_observability.py`. ✅

- LOW — Not propagated into Prometheus labels (intentional — would explode cardinality).
- LOW — Not propagated into LLM provider HTTP requests as a header (e.g., `X-Request-Id`). Adding it would let upstream provider logs correlate with Helix runs.

### 3.4 Token budget enforcement

`_token_budget()` / `_allocate_prompt_budget()` is enforced ONCE per `execute_agent_skill` call. After truncation, the resulting prompts are NOT re-measured against the actual token count of the model — the char-based estimate is the final word. Two risks:

- A non-English requirement (CJK languages: 1 char ≈ 1 token) will under-budget by ~3-4×. A Japanese requirement of 1000 chars estimated as 250 tokens is actually ~1000 tokens.
- Markdown code fences vs prose have different ratios.

Worth replacing the char heuristic with `tiktoken` for OpenAI-family models (it's already in the lock file via `pydantic-ai-slim`). For other providers, char-based is still the only option.

### 3.5 Mode (llm vs mock) reporting

Every run records its `mode` in:
- `AgentRunResult.mode`
- Artifact frontmatter `llm_mode`
- Prometheus label `mode`
- Worker `persist_workflow_step_activity` field `provider_name=step_data["mode"]`

Consistent. ✅

- LOW — The `provider_name` field in WorkflowStep is being filled with `mode` ("pydantic_ai"/"httpx"/"mock"), not the actual provider name ("openai"/"anthropic"/etc.). Semantic mismatch — the database column suggests it stores the LLM provider, but it stores the transport. Worth adding a separate `transport_mode` column or remapping.

---

## 4. Severity summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 7 |
| MED | 13 |
| LOW | ~110 |

HIGH issues:

1. PydanticAI client mutates `os.environ` with API keys — not thread-safe and may leak.
2. PydanticAI client never passes `base_url` to non-OpenAI compatibles — DeepSeek/OpenRouter/Custom/Local typed-path always hits OpenAI.
3. Gemini provider puts API key in URL query string — leaks via httpx logs, OTLP spans, exception messages.
4. `agents.runtime.bmad_executor._resolve_provider_for_org` + `llm_client.call_llm` import `app.db.session.SessionLocal` — incomplete worker DB decoupling, drags backend init into worker processes.
5. `agents.runtime.bmad_loader.load_bmad_agent` resolves `persistent_facts` non-glob entries with no project-root containment check — malicious `customize.toml` could read arbitrary file.
6. Bedrock AWS secret access keys appear to live in `extra_config` unencrypted (needs schema confirmation).
7. Transport order `pydantic_ai` first incurs longer first-failure latency than `httpx` — combined with HIGH#1 + HIGH#2 this is the slowest AND riskiest path.

---

## 5. Top 10 prioritized fixes

1. **`agents/runtime/pydantic_ai_client.py:76-101`** — Stop writing API keys to `os.environ`. Use PydanticAI's explicit provider constructors (`OpenAIProvider(api_key=..., base_url=...)`) so concurrent activities don't race on env vars and so non-OpenAI base URLs actually get used.
2. **`agents/runtime/providers/gemini_provider.py:28`** — Move the API key from the URL query string to a header (`x-goog-api-key`). Closes the OTLP/log leak surface.
3. **`agents/runtime/bmad_executor.py:355-399` and `agents/runtime/llm_client.py:26`** — Switch the org-scope provider lookups to use `worker.db.session.SessionLocal` when running inside a worker process (detect via `temporalio.activity.in_activity()`), or move the lookup into an explicit "resolver" abstraction that both processes can implement.
4. **`agents/runtime/bmad_loader.py:312-320`** — Add `path.is_relative_to(project_root())` to the persistent_facts resolution loop. Reject any entry that escapes.
5. **`agents/runtime/bmad_executor.py:613-622`** — Don't fall back to mock when LLM output exists but fails parse — instead PERSIST the raw LLM output as an artifact with `parse_failed=True` in frontmatter, then attempt mock-on-top. Operators need to see what the LLM returned.
6. **`agents/runtime/bmad_executor.py:377-382`** — Pass the actual `agent_code` (not the literal `"bmad-agent"`) into `resolve_routing` for the PydanticAI path so per-agent LLM mappings work for typed calls.
7. **`agents/runtime/providers/anthropic_provider.py:36-41`** — Add `temperature` to the body. Default of 1.0 is hotter than Helix wants.
8. **`worker/activities/bmad_node_activities.py:302-329`** — Add idempotency to `persist_workflow_step_activity` — upsert on `(workflow_run_id, step_order)` to handle Temporal's at-most-once-but-actually-at-least-once delivery semantics.
9. **`worker/Dockerfile:40-43`** — Replace the Temporal-only healthcheck with a worker-liveness probe. The current check passes even when the worker process is dead.
10. **`worker/workflows/bmad_per_node_workflow.py:159-162`** — Catch `asyncio.TimeoutError` from `workflow.wait_condition(timeout=_APPROVAL_TIMEOUT)` and return a clean `status="expired"` instead of letting the workflow fail.

---

## 6. Architecture suggestions

**Static-analysis language detection.** Today only Python sources get the AST pass; non-Python sources fall to a regex-only secret scan. Many migrations involve SQL, JavaScript, Java, COBOL, Talend XML — high-value targets for static checks. Plug in language-specific lightweight analysers (e.g., `tree-sitter` bindings for SQL/JS/Java). Even partial parse trees would catch missing-semicolon, broad-catch, etc.

**Provider registry as entry points.** The current registry is hard-coded to ten built-in adapters with explicit imports in `providers/__init__.py`. A discovery mechanism via Python entry points (`setup.cfg [options.entry_points] helix.providers`) would let OSS users distribute custom adapters as separate pip packages without forking. The registry helper functions are already in place.

**Merge planning and per-node workflows.** Two workflows shipping today (planning monolith + per-node) sharing one task queue means activities `execute_bmad_graph_activity` and the 13 per-node activities are both registered. The monolithic workflow is now legacy (the facade routes new requests to `BMADPerNodeWorkflow`). Deprecate `BMADPlanningWorkflow` + `execute_bmad_graph_activity` in a release, then remove. One workflow class is easier to reason about and to operate.

**Transport order with budget-aware switching.** `pydantic_ai → httpx → mock` is fine when both transports succeed, but for slow networks the `pydantic_ai` cold-import + slow-fail can add 5–10s before `httpx` is tried. Make the order configurable per agent (some agents need typed output more than others) and provide a "httpx first, typed retry on success" mode for latency-sensitive paths.

**Replace char-based token estimate with provider-aware estimator.** `tiktoken` is already in the dep tree for OpenAI models. Use it when available; fall back to char-based for non-OpenAI. The current 4-chars-per-token rule underestimates CJK languages by 3–4× and breaks the budget on multilingual migrations.

**Connection pooling.** Every provider adapter calls `httpx.post(...)` synchronously — no pooled `httpx.Client`. Create one client per provider instance and pool keep-alive connections; modest latency reduction (~30-50ms per call) and reduced TCP-handshake noise.

**Idempotency keys on artifacts.** The artifact filename includes a timestamp (`YYYYMMDDTHHMMSSZ-<slug>.md`) — if a Temporal retry re-runs the same activity, you'll get TWO artifacts for the same logical step. Adding the workflow_run_id + step_order to the filename (`<wfid>-<step>-<slug>.md`) would make retries idempotent and let you garbage-collect failed runs cleanly.

**Read-only artifact-store getters.** `planning_root_for_project` and `implementation_root_for_project` always `mkdir`. Add a `_dir(project_id, *, ensure=False)` variant for read-only callers (e.g., `list_artifacts` shouldn't create the dir).

**Lifecycle of `_compiled_graph`.** The LangGraph compiled instance is cached at module level. Add a public `reset_graph_cache()` that LangGraph node changes in dev can call without restarting the worker.

**Workflow versioning.** Today the per-node workflow has 13 hard-coded steps. Adding a step or changing order will break in-flight workflows (Temporal will fail to resume). Use `workflow.patched("add-step-foo")` from temporalio.workflow to version changes — pattern is well-documented and avoids backfill pain.

**Provider observability.** Add a Prometheus counter for `helix_llm_provider_calls_total` keyed by `(provider_type, model, outcome)` and a histogram `helix_llm_provider_latency_seconds`. Today metrics only exist at the BMAD-agent level — provider-level metrics would diagnose which provider/model is slowest.

**Secrets in artifact frontmatter.** The frontmatter currently records `correlation_id`, `prompt_tokens_estimate`, `pydantic_ai_available`, `llm_mode`. It does NOT (correctly) record api keys or provider URLs. Worth an explicit "no secrets in frontmatter" assertion in tests.

**`extra_config` encryption.** If AWS secret access keys live in `extra_config`, ensure the column is encrypted (or move AWS creds into a dedicated encrypted secret store like the existing `LLMProviderSecret` table). The current adapter docstring at `bedrock_provider.py:14-20` documents `aws_secret_access_key` as a plaintext key in `extra_config` — that's a footgun.

**Subprocess fallback observability.** `_run_bmad_script` falls back silently when the resolver script fails or times out. Add a counter `helix_bmad_resolver_fallback_total{kind="config"|"customization"}` so operators can spot resolver regressions.

**Streaming responses.** No provider adapter supports streaming. For multi-minute LLM calls, the worker has no token-by-token feedback — a frontend "agent is thinking..." status is impossible. Adding streaming to the OpenAI/Anthropic/Bedrock adapters (server-sent events) and forwarding to a Temporal heartbeat would unlock real-time progress UI.

**Backpressure on httpx.** No `httpx.Limits` configured. Default is 10 keep-alive connections / 100 max connections per process. With 100 concurrent BMAD activities × 1 LLM call each, you'd saturate. Set explicit `httpx.Limits(max_connections=20, max_keepalive_connections=10)` on a per-process httpx Client.

**Per-agent prompt budgets.** Today the budget is global (`HELIX_PROMPT_TOKEN_BUDGET`). Some agents (Winston architect) need bigger budgets; others (gate, code-review) need less. A per-agent override (`HELIX_PROMPT_BUDGET_WINSTON=20000`) would let operators tune without code changes.
