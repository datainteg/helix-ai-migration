# Helix Migration — Roadmap

Source of truth for "what's shipped vs what's next". Updated alongside the
commit log. Each section maps to deployable commits in `git log --oneline`.

---

## Shipped (12 commits since 2026-05-25 audit)

### Security + correctness baseline
- 18 CRITICAL + 86 HIGH findings from `docs/review/` closed.
- Audit chain HMAC isolated from JWT key; per-org advisory lock on chain writes.
- SSRF guard at admit + send time on webhooks.
- SSE auth via 60 s `scope=sse` ticket (sprints + workflow streams).
- Super-admin `imp_by` claim + audit on every super-admin endpoint.
- Background tasks own their `SessionLocal`.
- All SQL connectors run sync DB work via `asyncio.to_thread`.
- Security headers middleware: XCTO / XFO / Referrer / Permissions / HSTS.
- `/readyz` (DB-gated) + `/healthz` split.
- Frontend modal a11y primitive (`<Modal>` + `useFocusTrap`).

### Production-ready posture
- One-click `setup.sh` / `setup.ps1` provisioning + DR `backup.sh` / `restore.sh`.
- Docker: temporal-ui under `--profile debug`, frontend non-root.
- Frontend `/api/healthz` route.
- Optional dep imports gated (OTel, prometheus_fastapi_instrumentator).

### Migration-ops features
- Cutover state machine (`bulk → tail → freeze → diff → flip → done` /
  `rolled_back`) + admit-time + send-time guards.
- LLM cost tracking (`llm_usage_records`) + per-org daily/monthly USD cap +
  hard/soft enforcement + auto-recording inside BMAD executor.
- Daily cost rollup endpoint + real sparkline on `/admin/cost-limits`.
- Rollback artifact link (`rollback_artifact_id` self-FK) +
  `POST /artifacts/{id}/generate-rollback` LLM endpoint.
- Migration template catalog (5 starter packs) + clone-to-project.
- Slack `/helix` slash-command receiver (HMAC verified, 5-min window).
- Schema drift watcher (`POST schema-snapshots`, `GET drift`).
- Compliance PDF pack per project (audit chain + validation + recon +
  cutover + artifacts).
- Time-machine replay endpoint (`POST /workflows/{id}/replay`).
- AI pair-review endpoint (`POST /artifacts/{id}/pair-review`).
- CDC polling engine MVP (lifespan task stamps liveness on tail cutovers).
- Plugin marketplace catalog (7 community entries).
- RAG knowledge base MVP (upload + keyword search; vector-store seam left
  for the swap).

### Scale + ops
- Read-replica routing via `DATABASE_READ_URL` + `get_read_db()` dependency
  (dashboard stats endpoint switched).
- Per-org rate limiter (`org_limiter`) keyed on `X-Active-Org-Id` → JWT tail
  → IP.
- S3 / S3-compatible artifact storage driver (MinIO / R2 / B2 via
  `S3_ENDPOINT_URL`).
- Per-agent Temporal retry policy + 10 s activity heartbeats.

### Developer experience
- Helix CLI (`cli/`) with login / projects / workflow / cost / templates /
  cutover commands.
- Python SDK (`sdk/python/helix_sdk/`) — same surface as the CLI.
- TypeScript SDK (`sdk/typescript/`) — fetch-based, types exported.
- 10 LLM provider adapter unit tests (OpenAI, Anthropic, Gemini, DeepSeek,
  OpenRouter, Custom, Local, Bedrock, Vertex, Azure).
- Backend tests for: SSRF, secret_service, SSE ticket, worker idempotency,
  cutover, cost_service, migration_templates, slack signature, schema
  drift, marketplace, knowledge, CDC tick, daily cost rollup, prompt
  overrides.
- Playwright golden-path smoke.

### UI surface delta
- Sidebar: System gains "Cost limits"; Resources gains "Knowledge" +
  "Marketplace".
- Project tabs: "Cutover" + "Compliance".
- New pages: `/admin/cost-limits`, `/projects/[id]/cutover`,
  `/projects/[id]/compliance`, `/marketplace`, `/knowledge`.
- Dashboard tile: real LLM spend / top-provider / top-agent /
  input-output tokens.
- Validation hero: real org-wide pass rate.
- Drift watcher card mounted on cutover page.
- Demo data banner on 6 product pages.

---

## Pending — ordered by impact

### Wave A — close the loop on shipped features (≤ 1 week)
1. **HelixBMAD nodes pass `prompt_overrides`** — executor accepts; node
   callers don't pass yet. Without this, `/workflows/{id}/replay` only
   propagates overrides via concatenated `requirement_text`.
2. **Replay diff viewer page** — backend ships the new workflow id; UI has
   no side-by-side artifact diff.
3. **Pair-review button on artifact detail** — backend ships; no trigger
   in the artifact panel.
4. **CDC engine real source-poll + target-apply** — current loop only
   stamps liveness; production needs per-table watermarks + apply.
5. **Vector embeddings on `knowledge_docs`** — keyword search saturates at
   ~10 k docs; pgvector swap-in behind the same `/knowledge/search`
   contract.

### Wave B — test debt
6. Tests for the 9 most-recent endpoints: replay, pair-review, per-org
   limiter, read-replica routing, Python SDK round-trip, TS SDK
   round-trip, compliance PDF generator, CDC engine loop, daily cost.
7. Frontend Playwright on `/cutover`, `/cost-limits`, `/marketplace`,
   `/knowledge`.

### Wave C — operational maturity
8. Body-stream chunked upload validator (Content-Length-only today).
9. Idempotency keys on workflow start.
10. Per-vendor exact token counts (extract `usage` block from API
    responses instead of estimating).
11. Dead-letter inspection UI (failed activities + replay).
12. Read-replica wired beyond `/dashboard/stats` (project list, audit-log
    pagination).

### Wave D — DX + ecosystem
13. CLI: `helix migrate --plan` headless planner.
14. SDK: webhook + EventBridge subscribers.
15. VS Code extension for artifact review.
16. RAG with Confluence / Notion ingest pipeline (not just paste).
17. Workflow time-machine UI with diff-and-promote.

### Wave E — long-tail review backlog
- 230+ MED nits (N+1 query smells, error-handling edges).
- 257+ LOW nits (typography, dead imports, doc strings).

### Operator one-shot (manual, not code)
```bash
cd backend && alembic upgrade head           # all migrations
./scripts/generate-secrets.sh                # backfill AUDIT_HMAC_KEY
cd website && npm install --save-optional sharp && npm run build:og
cd sdk/python && pip install -e .
cd cli && pip install -e .
crontab -l  # add: 0 3 * * * /opt/helix/scripts/backup.sh
```

### Next-up picks for this batch
- Wave A items 1-5 (closes the loop on every shipped backend that lacks UI
  or end-to-end plumbing).
- Wave B item 6 (regression safety on new endpoints).

The two combined leave only items that need new feature design (Wave C+D),
not bug-fix follow-up.
