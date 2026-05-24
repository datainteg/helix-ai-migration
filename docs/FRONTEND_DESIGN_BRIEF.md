# Helix Migration — Frontend Design Brief (for Claude design)

Paste this verbatim into Claude design when redesigning the Helix Migration
frontend. Includes the full product context, every screen we need, the data
shapes the backend returns, and the design constraints.

---

## Product one-liner

**Helix Migration** is an open-source, AI-powered data migration + validation
platform. Six BMAD-METHOD agents (Mary, Paige, John, Sally, Winston, Amelia)
collaborate on a 13-step pipeline to plan, design, build, validate, and
document data migrations between source and target systems (Salesforce →
Snowflake, Oracle → Databricks, SQL Server → Snowflake, etc.).

## Who uses it

- **Admins** — configure LLM providers, map BMAD agents to models, manage
  users + RBAC, view audit logs, monitor system health.
- **Project managers / architects** — create migration projects, write
  requirements, approve agent plans at the human-in-the-loop gate, review
  artifacts.
- **Data engineers / QA** — inspect agent outputs (PRD, architecture, dev
  story, code, tests), trigger validation runs, drill into reconciliation
  results.
- **Developer Workspace users** — upload code artifacts (`.py`, `.sql`),
  trigger BMAD code review + investigation on uploaded files.

## Tech stack

- Next.js 14 (App Router), TypeScript, Tailwind CSS
- React Query for server state, Zustand for UI state, Context API for auth
- Custom UI primitives (no Shadcn / MUI) — keep that pattern in the redesign
- Lucide React icons
- All API calls go to a FastAPI backend at `${NEXT_PUBLIC_API_URL}/api/v1/...`

## Visual direction

- Color: indigo / violet / cyan accents on a near-white canvas. Helix's
  identity color scale lives under `helix-*` Tailwind tokens.
- Density: dense-but-airy enterprise dashboards. Think Linear / Vercel /
  Stripe — not Bootstrap.
- Typography: small UI text (12.5–14 px), generous numeric font for metrics
  + IDs, monospace for IDs / paths / model names.
- Layout: persistent left sidebar (≈ 248 px), top topbar with project
  selector + user menu, main content area with PageHero (breadcrumbs +
  title + subtitle + actions) followed by Card-based grid.
- Dark mode toggle exists but design system already light-first.
- No tables-for-layout. Use real `<table>` for tabular data, grid for cards.

## Sitemap (every page)

### Marketing / Auth

- `/` — landing page. Hero, feature cards, BMAD agent grid, pricing teaser,
  architecture diagram, CTAs to install + setup.
- `/login` — email + password.
- `/setup/first-admin` — first-run onboarding: create org + first admin.

### Authenticated shell

All pages below sit inside `AppShell` (left sidebar + topbar + main).

#### Migration core

- `/dashboard` — Migration Command Center. Metric strip (total projects,
  validation pass %, recon score %, pending approvals, agent success rate),
  weekly migration trend area chart, validation distribution donut,
  project risk heatmap, recent activity feed, top 4 active agents grid,
  projects-at-risk table.

- `/projects` — paginated list of all migration projects. Search,
  status filter, sort. Each row: name, source → target, owner, progress
  bar, validation %, recon %, last updated, status badge.

- `/projects/new` — create form.

- `/projects/[id]` — project detail. Tabs: Overview (metric mini-cards,
  source/target connectors, owner, environment), Requirements (textarea +
  "Generate Plan" button), Agent Workflow (live BMAD canvas — see below),
  Validation, Reconciliation, Artifacts, Settings.

- `/projects/[id]/agents` — project-scoped agent workflow (subset of /agents
  but pinned to one project).

- `/projects/[id]/developer-workspace` — project-scoped IDE.

#### Agent workflow (the centerpiece)

- `/agents` — global view of all running BMAD workflows. Left: workflow
  list (workflow_id, status badge, created_at). Center: 13-node BMAD
  pipeline canvas — vertical chain with status per node + per-node provider
  chip + clickable artifact icon. Right: workflow details panel (status,
  mode, completion count, approval gate buttons when waiting, artifact
  links). Clicking an artifact opens a modal with the full markdown.

  Critical: the 13 nodes are fixed and named:
  1. Winston — Project Context (Phase 0)
  2. Mary — Product Brief (Phase 1)
  3. John — PRD (Phase 2)
  4. Sally — UX Design (Phase 2)
  5. Winston — Architecture (Phase 3)
  6. Winston — Epics & Stories (Phase 3)
  7. Winston — Readiness Check (Phase 3)
  8. **Human Approval Gate** (conditional branch)
  9. Amelia — Story File (Phase 4)
  10. Amelia — Implementation (Phase 4)
  11. Amelia — QA Tests (Phase 4)
  12. Amelia — Code Review (Phase 4)
  13. Paige — Documentation (Phase 5)

  Each node renders: phase label, agent name + skill, status (pending /
  running / completed / failed / rejected), provider chip (pydantic_ai /
  llm / mock), artifact-link icon. Visualize the conditional branch after
  the approval gate clearly — approved continues down, rejected ends the
  flow.

#### Validation + Reconciliation

- `/validation` — Validation Center. Metric cards (total / passed / failed
  / warnings / pass rate). Type tabs (all, row_count, schema, null,
  duplicate, distribution, business_rule). Searchable check table
  (name, type, source → target, last run, owner, status). Distribution
  donut + recent failures sidebar.

- `/reconciliation` — Reconciliation Center. Metric cards (recon score,
  matched, mismatched %, missing, avg row score). 12-week trend area chart.
  Mismatch categories donut. Top anomalies list. Recon jobs table.

#### Developer Workspace

- `/developer-workspace` — artifact upload + list. Left: project picker +
  file upload (`.py` / `.sql`). Right: artifacts table (filename, hash,
  uploaded date, view-and-review link).

- `/developer-workspace/[id]` — three-pane IDE. Left: artifact tree +
  versions. Center: source code viewer / generated draft / diff viewer /
  notebook tabs. Right: AI review panel with findings, blockers, sign-off.

#### Connectors

- `/connectors` — grid of cards for built-in + custom connectors.
  Each card: type icon, name, vendor, capability chips, status badge,
  Configure + Test buttons. **Currently missing: the credential modal +
  test flow when buttons are clicked. The redesign should propose how
  this should look (modal form with provider-specific fields,
  test-connection feedback, save action).**

#### Admin

- `/admin` — admin hub. 4 metric cards (users, providers, system health,
  audit events / day). Grid of 10 admin tiles linking to sub-pages.

- `/admin/users` — user table + invite flow + role assignment.

- `/admin/llm-settings` — list of configured LLM providers (OpenAI,
  Anthropic, Gemini, DeepSeek, OpenRouter, custom OpenAI-compatible,
  local Ollama). Add provider form (type, name, base_url, default model,
  API key). Test connection action.

- `/admin/agent-mapping` — table mapping each of the 6 BMAD agents (Mary,
  Paige, John, Sally, Winston, Amelia) to a configured LLM provider +
  model + temperature + max tokens. Simple-vs-advanced routing toggle.

- `/admin/audit-logs` — paginated audit log table with CSV export,
  filter by actor / action / entity_type / date range.

- `/admin/system-health` — backend / database / Redis / Temporal / worker
  / connector pool status cards + latency + detail. Refresh button.

- `/admin/agent-mapping`, `/admin/system-health` — above.

#### Reports, templates, plugins, files (lower priority)

- `/reports` — report generation + history.
- `/templates` — migration templates / blueprint library.
- `/plugins` — plugin marketplace (community connectors / agents).
- `/files` — file browser into the artifact store.

## Data shapes the backend returns

### Workflow status (used by `/agents`)

```json
{
  "workflow_id": "bmad-proj-001-req-1",
  "run_id": "...",
  "status": "running",     // pending | running | completed | rejected | failed
  "mode": "temporal",      // temporal | local_fallback
  "project_id": "...",
  "requirement_id": "...",
  "created_at": "2026-05-25T12:34:56",
  "steps": [
    {
      "agent_name": "project_context",
      "step_order": 1,
      "status": "completed",
      "parsed_output": { /* AnalystOutput | PMOutput | ... */ },
      "artifact_path": "/app/data/.../bmad-agent-architect/20260525...md",
      "provider_name": "llm",      // pydantic_ai | llm | mock
      "model_name": "claude-sonnet-4-6",
      "error_message": null,
      "created_at": "..."
    },
    /* ...12 more... */
  ]
}
```

### BMAD agent output (one variant per agent — shared shape)

```json
{
  "summary": "...",
  "business_goals": ["..."],
  "open_questions": ["..."],
  "assumptions": ["..."],
  "risks": [{ "title": "...", "severity": "medium",
              "impact": "...", "mitigation": "..." }],
  "artifacts": [{ "filename": "product-brief", "path": "...",
                  "summary": "..." }]
}
```

### LLM Provider (for `/admin/llm-settings`)

```json
{
  "id": "...",
  "name": "OpenAI Prod",
  "provider_type": "openai",       // openai | anthropic | google | deepseek | openrouter | custom | local
  "base_url": "https://api.openai.com/v1",
  "default_model": "gpt-4.1",
  "api_key_masked": "sk-***...xyz",
  "status": "active"
}
```

### LLM Agent Mapping (for `/admin/agent-mapping`)

```json
{
  "agent_type": "bmad-agent-analyst",   // one of: bmad-agent-{analyst,tech-writer,pm,ux-designer,architect,dev}
  "provider_id": "...",
  "model": "claude-sonnet-4-6",
  "temperature": 0.2,
  "max_tokens": 4096
}
```

### Connector entry (for `/connectors`)

```json
{
  "id": "postgres",
  "connector_type": "postgres",
  "name": "PostgreSQL",
  "vendor": "PostgreSQL",
  "capabilities": ["read_data", "write_data", "schema_discovery", "row_count"],
  "status": "active"
}
```

## Design constraints

- **Empty states everywhere.** Backend is real — no mock data — so most
  pages start empty on a fresh install. Every page needs a clean empty
  state (icon + headline + description + primary CTA).
- **Loading + error states** as standard components, not afterthoughts.
- **Status badges** are reused everywhere: pending (gray), running (blue,
  optionally pulsing), completed (emerald), failed (red), rejected (amber),
  draft (indigo), queued (zinc).
- **All write actions hit real endpoints** — design needs primary action
  buttons that respect loading state + confirmation flows for destructive
  ops.
- **Role-based nav:** admins see `/admin/*` tiles; non-admins do not.
- **Responsive:** mobile is read-only acceptable but tablet + desktop must
  be first-class.
- **Accessibility:** keyboard nav, focus rings, ARIA labels on icon-only
  buttons.
- **No emoji in the design itself.** They show up in BMAD agent metadata
  (📊 Mary, 🏗️ Winston, etc.) — that's fine to render as data, but the
  chrome shouldn't use emoji.

## What the redesign should focus on improving

1. **Agent workflow visualization** — the 13-node BMAD pipeline is the
   product's headline. Current rendering is a vertical stack of pill
   cards. Open question: is there a better layout (Sankey? swim lanes
   per phase? branching diagram showing the conditional approval gate)?

2. **Connector configuration flow** — currently the "Configure" + "Test"
   buttons on `/connectors` are inert. We need: provider-specific form
   (the fields differ for Postgres vs S3 vs CSV upload), a test-connection
   step, a "save + persist" step, an optional "discover schemas" step.

3. **Developer Workspace** — three-pane IDE with diff viewer feels right
   but the right-side AI review panel needs a stronger pattern for showing
   findings categorized by severity, with inline links to the markdown
   artifact.

4. **Admin onboarding journey** — first-time admin lands on
   `/admin/llm-settings`. Then `/admin/agent-mapping`. Then back to
   `/projects/new`. This sequence should feel guided (progress indicator?
   wizard?), not five disconnected admin pages.

5. **Approval gate UX** — currently a side panel with Approve/Reject
   buttons that only appear after the readiness check. Open question:
   should this be a full-page interrupt? A modal? A persistent banner?

## Out of scope for the redesign

- Backend API changes (the endpoints are fixed).
- Auth flow (JWT + bearer header — keep current pattern).
- Routing structure (App Router stays; page paths above are canonical).
- Tailwind tokens (`helix-*`, `ink-*`, `surface-*`) — extend, don't
  replace.

## Deliverable

Updated `frontend/src/` source tree with the same page paths as above,
keeping React Query + Zustand + auth-context wiring intact. Components
should still export from `@/components/ui/*` and `@/components/layout/*`
for compatibility with existing imports.
