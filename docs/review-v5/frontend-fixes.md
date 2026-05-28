# Frontend Fixes — review-v5

Branch: `upgrade/review-and-fix`. Scope: `frontend/` only. No new npm deps, no framework
switch, no route changes, visual style preserved.

## Files changed

- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/projects/page.tsx`
- `frontend/src/app/projects/[id]/sprints/page.tsx`
- `frontend/src/app/projects/[id]/sprints/analytics/page.tsx`
- `frontend/src/app/projects/[id]/sprints/risks/page.tsx`
- `frontend/src/app/projects/[id]/sprints/timeline/page.tsx`
- `frontend/src/app/developer-workspace/page.tsx`
- `frontend/src/app/admin/page.tsx`
- `frontend/src/app/admin/users/page.tsx`
- `frontend/src/app/admin/system-health/page.tsx`
- `frontend/src/app/connectors/page.tsx`
- `frontend/src/app/agents/page.tsx`
- `frontend/src/app/reconciliation/page.tsx`
- `frontend/src/app/validation/page.tsx`
- `frontend/src/components/layout/PageHero.tsx`
- `frontend/src/components/ui/Card.tsx`
- `frontend/src/lib/use-api.ts`
- `frontend/src/lib/api/client.ts`

## New files created

- `frontend/src/app/loading.tsx` — route-level loading boundary using `<LoadingState>`.
- `frontend/src/app/error.tsx` — `"use client"` route-level error boundary using `<ErrorBanner>` + Try-again (`reset`) + Back-to-dashboard.
- `frontend/src/app/not-found.tsx` — clean 404 with links back to dashboard / projects.

## Per-finding status

### UI/UX

- **UI-001 — Metric strips collapse on phones**: FIXED.
  - `dashboard/page.tsx:149` → `grid-cols-2 sm:grid-cols-3 lg:grid-cols-5` (+ reflowing dividers).
  - LLM-spend row (`dashboard` `sm:grid-cols-4`) given reflowing `divide-y sm:divide-y-0 sm:divide-x`.
  - `projects/page.tsx:132` → `grid-cols-2 sm:grid-cols-3 lg:grid-cols-6` (+ dividers).
  - `sprints/page.tsx:223` → `grid-cols-2 sm:grid-cols-3 lg:grid-cols-5` (+ dividers).
  - `sprints/analytics/page.tsx:171` → `grid-cols-2 sm:grid-cols-3 lg:grid-cols-5` (+ dividers).
  - `sprints/risks/page.tsx:172` (6-cell strip) → `grid-cols-2 sm:grid-cols-3 lg:grid-cols-6` (+ dividers).
  - Risks heatmap (the inner 5×5 matrix at lines ~268/303): **intentionally left as `grid-cols-5`**. It is a fixed-geometry likelihood×impact heatmap (200px tall, 5 columns are axis buckets), not a metric strip — collapsing it to one column would destroy the visualization. The whole heatmap card now sits full-width below `xl` (via the UI-003 fix), so it has room. Noted as a deliberate deviation from the literal `grid-cols-1 md:grid-cols-5` suggestion.
- **UI-002 — Developer workspace IDE fixed columns**: FIXED (minimum-viable, desktop-first preserved).
  - Outer three-pane grid wrapped in `<div className="overflow-x-auto">`.
  - All three grid children given `min-w-0` (center pane wrapped in a new `min-w-0 overflow-hidden` div).
  - `gridTemplateColumns` is now computed from `showLeftPane`/`showRightPane` state (`useState`, default true).
  - Added "Show/Hide files" toggle (visible `md:hidden`) and "Show/Hide review" toggle (visible `lg:hidden`) in the header action row; both `aria-pressed` + `aria-label`. Desktop (lg+) always renders all three panes; toggles only surface on small screens.
- **UI-003 — Sprint risks fixed columns**: FIXED. `risks/page.tsx:181` `grid-cols-[1fr_320px]` → `grid-cols-1 xl:grid-cols-[1fr_320px]`.
- **UI-004 — Dead admin tiles**: FIXED. Identified the 5 dead routes (`roles`, `connectors`, `custom-connectors`, `notifications`, `import-export`). They now render as non-navigable `<div aria-disabled cursor-default opacity-60>` with a `<Chip>Coming soon</Chip>`. The 5 working tiles (`users`, `llm-settings`, `agent-mapping`, `system-health`, `audit-logs`) remain `<Link>`s.
- **UI-005 — Missing route-level error/loading/not-found**: FIXED. Created the three files listed above.
- **UI-006 — `PageHero` unresponsive padding**: FIXED. `px-10 pt-8 pb-6` → `px-4 sm:px-6 lg:px-10 pt-8 pb-6` (matches AppShell body).
- **UI-007 — Dashboard chart rows force 3 cols**: FIXED. All three `grid grid-cols-3` rows → `grid grid-cols-1 lg:grid-cols-3`. `AreaChart width={760}` wrapped in `w-full overflow-x-auto`. (Donut `size={132}` already lives in a flex row that reflows; left untouched to avoid refactoring the chart component.)
- **UI-008 — Workspace search inputs unlabeled**: FIXED. Both inputs (`Search files…` and `Explain this migration step…`) got `aria-label` + `focus-ring` appended to the existing `outline-none`.
- **UI-009 — Icon-only buttons missing `aria-label`**: FIXED. Added `aria-label="More actions"` to `projects/page.tsx:168` and `agents/page.tsx:278`. Grep confirmed these are the only two `size="icon"` instances in `src/`.
- **UI-010 — Connector search input no focus-ring**: FIXED. Added `focus-ring` and `aria-label="Search connectors"` to the input in `connectors/page.tsx`.
- **UI-011 — Reconciliation mock with no-op CTA**: FIXED. Added a `<DemoBanner>` ("Reconciliation API not yet enabled — see Settings → Reconciliation…") at top of body; disabled the "Run Reconciliation" button + `title="Reconciliation API not yet enabled"`. No backend wiring (no route exists).
- **UI-012 — Validation page mixes demo + real**: FIXED. The fabricated `VALIDATION_CHECKS` table and `TYPE_BREAKDOWN` panel now render only when `hasProjects !== true`. When real projects exist (`hasProjects === true`), both render an `<EmptyState>` ("No validation rules yet — Create rule" / "No category data yet"). `<DemoBanner>` stays above the fold for both states.
- **UI-013 — Sprint timeline SVG fixed 1100px**: FIXED. The `<svg>` was already inside `overflow-x-auto`; additionally added `width="100%"`, `viewBox="0 0 1100 …"`, `preserveAspectRatio="xMinYMin meet"`, and `min-width: 1100` so it scales down smoothly yet never sub-renders the gantt.
- **UI-014 — `Card.title` not a heading**: FIXED. `Card` now renders `title` via an `as?: "h2" | "h3" | "div"` prop (default `"h2"`). Existing callers unchanged (default applies); tsc clean across all callers.
- **UI-015 — Admin tables no overflow wrapper**: FIXED. Wrapped both `<table>`s (`admin/users`, `admin/system-health`) in `<div className="overflow-x-auto table-scroll">`.
- **UI-016 — Inline-style page styling diverges from tokens**: DEFERRED (per instruction). See notes below.
- **UI-017 — Reconciliation raw palette**: FIXED. `bg-amber-50 border-amber-200 text-amber-800` → `bg-warn-soft border-hx text-warn`; `text-amber-700` → `text-warn`; `text-emerald-700` → `text-ok`; `bg-zinc-50/70` → `bg-app-2`; the `hover:bg-zinc-50/60` row hover → `hover:bg-surface-hi`. All target utilities verified present in `globals.css`.
- **UI-018 — Divider doesn't reflow**: FIXED (folded into UI-001). Replaced bare `divide-x` with `divide-y {bp}:divide-y-0 {bp}:divide-x` on every metric strip so dividers reflow with the grid.

### Code

- **H-017 — `useApi.handleResponse` breaks on 204**: FIXED. Added `if (res.status === 204 || res.headers.get("content-length") === "0") return undefined as T;` before `res.json()`. Audited the parallel client (`lib/api/client.ts`, per M-017): same bug existed in `apiGet`/`apiPost`; extracted a shared `parseBody(res)` guard applied to both.

## Typecheck result

`cd frontend && npx tsc --noEmit` → **clean, zero errors.** (ESLint not configured in the repo — `next lint` prompts to initialize — so relied on tsc, which validates JSX structure + types across all edited files.)

## UI-016 (deferred) notes

UI-016 calls for replacing the hundreds of inline `style={{ padding, fontSize, … }}` pixel
literals in `developer-workspace/page.tsx` (lines ~175–870), `setup/first-admin/page.tsx`,
`connectors/page.tsx` (~1080–1098), and `approval/page.tsx` (~31–95) with Tailwind utilities /
CSS vars so they track the `--tweak-font-size` / density / dark-mode knobs.

Deferred because:
- It is a large, low-risk-but-high-churn refactor touching 4 files and many hundreds of
  style props — out of proportion to a "responsive/a11y fixes, not a redesign" pass, and the
  highest-volume file (`developer-workspace`) is partly outside the safe-to-touch set for
  deeper edits.
- Pure-cosmetic; no functional/a11y regression today. The token-tweak panel simply doesn't
  reach these regions yet.

Scope estimate: ~1–1.5 days. `developer-workspace` alone is ~6–8h (≈200 inline style blocks,
each needing a token/utility mapping + visual regression check at 3 breakpoints). The other
three files are ~1–2h each. Recommend doing it file-by-file behind a screenshot diff, and
adding an ESLint rule (`react/forbid-dom-props` style or a custom rule) to forbid new inline
pixel literals once migrated.

## Not addressed (out of scope for this pass)

Medium/Low UI findings UI-019..UI-046 and code findings other than H-017 were not in the
assigned list. A few were touched incidentally: UI-028 (projects filter bar) was NOT widened
with `flex-wrap` since it wasn't in scope; UI-025 (`MetricCell` truncate) not applied —
flagged for a follow-up since the UI-001 reflow makes cells narrower.
