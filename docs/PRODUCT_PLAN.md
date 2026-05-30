# Helix — Master Product Plan

> Authoritative plan. Design only (no code yet). Two companion docs:
> - `docs/DEMO_MODE_PLAN.md` — full demo/real mechanics, API contracts, migration checklist
> - this file — product vision, lean-core build approach, phased rollout

---

## 1. Product vision (the two-mode model)

Helix is an **AI-assisted database migration tool** (DB→DB: e.g. Oracle→Postgres,
on-prem→Snowflake). It ships in **two modes that share one codebase and one set of APIs** —
the only difference is *which organization's data* the logged-in user is scoped to.

| Mode | Who | Purpose | Data source |
|------|-----|---------|-------------|
| **Demo user** | Anyone (one click) | **Learn & understand** the platform with a fully populated, realistic example | A seeded **demo organization** in Postgres, served by the real APIs |
| **Real user** | Admin / normal accounts | Run actual migrations on **their own data** | Their own organization's real data, original production architecture |

**Principle:** demo mode is NOT a separate app, fake data, or a frontend bypass.
It is a *real account* in a *real seeded org* hitting the *same APIs*. Real users are a
different org. Isolation is structural (multi-tenant by `organization_id`), so:
- a real user can **never** see demo data, and
- a demo user can **never** touch real data —
without any per-feature special-casing.

---

## 2. The golden path (what both modes do)

Everything serves ONE end-to-end flow. Demo users see it pre-completed; real users run it live.

```
  New project → connect source/target → generate migration → watch agents → reconciliation report
     │              │                       │                    │                │
   name +        real DB conn          AI agent chain        live steps +     counts + checksums
   src/tgt       or upload DDL         (below)               artifacts        + sampled diffs
                                                                              "98.7% verified"
```

### The AI agent chain (repurposed from the generic BMAD pipeline)

The existing 13-node BMAD pipeline is a **software-product SDLC** (analyst→PM→UX→
architect→dev→QA→docs) — the wrong shape for DB migration. Replace the personas with a
**migration-specific chain** (reusing the Temporal orchestration, approval gate, and
artifact store as-is):

```
SchemaAnalyst  →  TypeMapper      →  ScriptGenerator  →  Reconciler  →  [human approval gate]
read source       target types +     DDL + data-move      verify src vs tgt
schema/DDL        transforms +       SQL + rollback        counts/checksums
                  flag ambiguous     scripts               + sampled value diff
```

### Where the AI must win (the wedge)
1. **Semantic** type mapping (Oracle `NUMBER(p,s)`/`CLOB`/sequences/identity/triggers/PLSQL → correct target equivalents), not syntactic.
2. **Explain every mapping decision** — trust over magic.
3. **Flag risky/ambiguous mappings** for human review (the approval gate already exists).
4. **Prove correctness** — reconciliation is the close (buyers' #1 fear: "did my data move correctly?"). Dry-run first via the existing `SAFE_EXECUTION_MODE=analysis_only`.

---

## 3. Architecture: demo vs real

```
                        Same Next.js app · same FastAPI · same APIs · same Postgres
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  /login                                                                       │
  │    ├── "Sign In"            → POST /auth/login      → cookie → user's real org │
  │    └── "Login with Demo User" → POST /auth/demo-login → cookie → DEMO org      │
  │           (button shown iff NEXT_PUBLIC_DEMO_ENABLED; endpoint gated by        │
  │            ALLOW_DEMO_LOGIN)                                                   │
  └─────────────────────────────────────────────────────────────────────────────┘
                                   │
                    every request carries the helix_token cookie
                                   │
                  get_current_organization_id  ← scopes ALL queries to the
                  (the user's single active org membership)   logged-in org
                                   │
        ┌──────────────────────────┴───────────────────────────┐
        ▼                                                        ▼
   DEMO ORG (is_demo=true, seeded)                       REAL ORG(s) (customer data)
   read-only role → mutations 403                        full RBAC, live agents/Temporal
```

- **Demo login:** new public `POST /api/v1/auth/demo-login`, mints the **same** `helix_token`
  cookie via existing auth code. No password on the wire, no client bypass.
- **Demo is read-only (v1):** demo user gets the existing `viewer` role → backend `403`s every
  mutation; write/start/approve buttons are disabled with a "Read-only demo" tooltip. (Avoids
  concurrent demo sessions corrupting shared data; per-session ephemeral org = v2.)
- **Flags:** `ALLOW_DEMO_LOGIN` (backend) + `NEXT_PUBLIC_DEMO_ENABLED` (frontend build).
  **`APP_ENV` is NOT reused** (it's load-bearing for cookie-Secure/Temporal/SSRF).
- Full mechanics, isolation proof, and per-router verification: see `docs/DEMO_MODE_PLAN.md`.

---

## 4. Lean core — keep vs park

Validating the idea ≠ finishing 44 pages. Carve a focused core from Helix; hide the rest from
nav (don't delete — park).

**KEEP & make real (the golden path):**
- Auth + the new demo-login
- Projects (list / new / detail)
- Connectors (source/target) — **fix the fake test + no-op save** so you can point at a real DB or upload DDL
- The migration agent chain (§2) wired to one real LLM provider
- **Reconciliation** — make counts + checksums + sampled diff real (the trust feature)
- Artifacts (target DDL, migration scripts, mapping rationale)
- Models: organizations/users, projects, connectors/sources/targets, workflow_runs/steps, recon_runs/results, schema_snapshots, artifacts, llm_providers

**PARK (hide from nav until core proven):** sprints (8 pages), cutover, marketplace, knowledge,
plugins, the dashboards' lower halves, dev-workspace IDE, validation-as-separate-module. (~30 of 44 pages.)

**Demo pages (5):** project → connect → generate → watch agents → reconciliation report.
These are the only pages the demo user needs to "understand how the platform works."

---

## 5. Demo data strategy (Postgres seed)

Seed the demo org so the 5 golden-path pages are production-rich:
- 1–2 demo **projects** (e.g. "Oracle HR → Postgres"), with source/target connectors + a sample schema
- A **completed migration run**: real `workflow_runs` + `workflow_steps` (SchemaAnalyst…Reconciler) with real-looking artifacts (target DDL, migration SQL, mapping doc)
- A **reconciliation result** with realistic numbers (matched/mismatched, a few flagged type mismatches)
- `audit_logs` entries, `llm_providers` (a demo provider), light cost/usage

Seeder = idempotent `app/services/demo_seed.py` (modeled on existing `sprint_seed.py`),
invoked on first demo-login (or via CLI). FK order + audit/encryption constraints per
`docs/DEMO_MODE_PLAN.md §5`. The demo is seeded **from a real completed run** so it's
genuinely representative, not fabricated.

---

## 6. Phased rollout

```
Phase A — Golden path REAL (backend-first)         the substance; no demo yet
  A1 Connectors: real test + save (fix the 2 bugs)
  A2 Migration agent chain (SchemaAnalyst→TypeMapper→ScriptGenerator→Reconciler) on a real schema
  A3 Reconciliation real (counts/checksums/sampled diff)
  A4 Artifacts (DDL, scripts, rationale)

Phase B — Thin UI                                   wire ONLY the 5 golden-path pages; park the rest

Phase C — Two-mode (the demo-user idea)             demo org + /auth/demo-login + button + seeder
  C1 organizations.is_demo + ALLOW_DEMO_LOGIN/NEXT_PUBLIC_DEMO_ENABLED flags
  C2 demo_seed.py — seed from a real Phase-A run
  C3 /auth/demo-login + "Login with Demo User" button + read-only role + disabled-mutation UX
  C4 isolation tests (real never sees demo; demo 403s writes)

Phase D — Polish to a design-partner demo           one canned Oracle→Postgres scenario, live end-to-end
```

**Why this order:** the demo user can only "teach the platform" if the platform actually does
something (Phase A). Demo mode (C) seeds from a real run, so it's representative. Parking the
30 extra pages (B) keeps focus until the core is proven.

---

## 7. Immediate next steps (proposed)

1. **Phase A1** — fix connectors (real `POST /connectors/test` + real save) so we can ingest a real source schema. Small, unblocks everything. (Also clears one of the 2 audit bugs.)
2. **Ground the agent chain** — verify how close the current pipeline + a real LLM provider get to producing migration SQL from a real schema, then design the 4-node migration chain concretely.
3. Then A2→A4, then the two-mode wiring (C).

Open question for you: should the migration agent chain **replace** the BMAD personas, or run
**alongside** them (BMAD kept for a future "build an app" use-case)? Recommendation: replace for
the DB-migration product; keep BMAD code parked, not deleted.
