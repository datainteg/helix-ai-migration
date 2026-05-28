# UI/UX Review

## Summary

- Findings: **Critical 3 / High 14 / Medium 18 / Low 11** (46 total)
- Top systemic issues:
  1. **Responsive collapse missing on dashboard-class layouts.** Multiple `grid-cols-5` / `grid-cols-6` metric strips and three `grid-cols-3` chart rows on `/dashboard`, `/projects`, `/projects/[id]/sprints/*` are not reduced at `sm`/`md`. Result: 5–6 cells per row at 320–375 px, each ≈45 px wide. Numbers truncate, charts render unreadable.
  2. **No global error/loading boundaries.** Zero `loading.tsx`, zero `error.tsx`, no `not-found.tsx`. A failing fetch on a route that doesn't handle it client-side (e.g. `/admin/audit-logs`, `/admin/cost-limits`) renders blank, and any unknown URL falls through to the framework's default 404.
  3. **`AppShell` body padding is responsive (`px-4 sm:px-6 lg:px-10`) but `PageHero` is hardcoded `px-10` (40 px).** Hero misaligns under its own container on mobile and pushes content overflow.
  4. **Mixed styling conventions.** Some pages use design-token utilities (`bg-app-2`, `text-ink-3`), but `developer-workspace/page.tsx`, parts of `connectors/page.tsx`, the `reconciliation` page, and parts of `setup/first-admin` reach for inline `style={{}}` or raw `bg-amber-50` / `text-emerald-700` colors. Two parallel "card" patterns coexist (Modal vs in-page bespoke modal in sprint board).
  5. **Dead links + stub pages.** `/admin` advertises 10 tiles but only 5 admin pages exist (Users, System Health, Audit Logs, Cost Limits, Agent Mapping, LLM Settings). Tiles for `roles`, `connectors`, `custom-connectors`, `notifications`, `import-export` link nowhere. Sidebar links to `/files`, `/reports`, `/templates`, `/plugins` resolve to "coming soon" stubs.

- Pages reviewed (sampled or read in full): `app/page.tsx`, `app/layout.tsx`, `login`, `dashboard`, `projects`, `projects/new`, `projects/[id]`, `projects/[id]/agents`, `projects/[id]/cutover`, `projects/[id]/sprints/board`, `projects/[id]/sprints/analytics`, `projects/[id]/sprints/risks`, `projects/[id]/sprints/timeline`, `agents`, `validation`, `reconciliation`, `connectors`, `knowledge`, `marketplace`, `developer-workspace`, `workflows/[id]/replay`, `artifacts/[id]`, `admin`, `admin/users`, `admin/system-health`, `admin/llm-settings`, `settings`, `setup/first-admin`, `approval`, `files`, `reports`, `templates`, `plugins`, all shared `components/ui/*`, all `components/layout/*`, `components/sprints/SprintKanbanBoard.tsx`, `website/index.html`, `website/.../Navbar.tsx`.
- Coverage gaps: Did not read full bodies of `admin/agent-mapping`, `admin/audit-logs`, `admin/cost-limits`, `projects/[id]/compliance`, `projects/[id]/developer-workspace`, `projects/[id]/sprints/{approval,dependencies,execution,mapping,releases}`, `projects/[id]/sprints/page.tsx`. These share the same `AppShell`/`Card`/grid patterns called out in CRITICAL/HIGH findings; specific per-page nits not enumerated.

## Findings

### CRITICAL

#### UI-001: Metric strips collapse to ~45 px columns on phones
- **File(s)**: `frontend/src/app/dashboard/page.tsx:149`, `frontend/src/app/projects/page.tsx:132`, `frontend/src/app/projects/[id]/sprints/page.tsx:223`, `frontend/src/app/projects/[id]/sprints/analytics/page.tsx:171`, `frontend/src/app/projects/[id]/sprints/risks/page.tsx:172` (also lines 268 & 303 use unguarded `grid-cols-5` for the risk heatmap)
- **Category**: responsive
- **Issue**: `grid grid-cols-5` and `grid grid-cols-6` are applied with no `sm:`/`md:`/`lg:` breakpoints. The dashboard hero metric strip puts 5 large numeric cells in one row regardless of viewport.
- **User impact**: At 320–375 px each cell is ≈45–55 px wide; "12,408,221" row counts wrap to 5 lines or get clipped by `overflow-hidden`. Page is unusable for triage on a phone.
- **Fix**: Use `grid-cols-2 sm:grid-cols-3 lg:grid-cols-5` (or `lg:grid-cols-6`) so dense strips reflow. Risks heatmap (5 buckets) should become a vertically stacked list under `md`.
- **Affected breakpoints**: 320 / 375 / 768

#### UI-002: Developer workspace IDE pinned to `260px 1fr 360px` with no fallback
- **File(s)**: `frontend/src/app/developer-workspace/page.tsx:755-761` (`gridTemplateColumns: "260px 1fr 360px"`, `height: calc(100vh - 44px - 81px)`)
- **Category**: responsive
- **Issue**: Three-pane IDE layout uses fixed-px columns, no breakpoint variant, no `overflow-x-auto` wrapper. Total min-width is 620 px just for the side rails; below ~1100 px the middle pane (diff viewer) gets <500 px and the AI-review pane's titles wrap to 4 lines.
- **User impact**: On a 1024 px laptop the diff is unreadable; on tablets/phones (≤768 px) the layout breaks entirely (panes overlap or get clipped). Pre-commit review is unusable away from a desktop.
- **Fix**: Either (a) stack panes vertically under `xl:` with disclosure buttons, or (b) make side panes collapsible to icons under `lg:`. Add `min-w-0` to every grid child and wrap the whole layout in `overflow-x-auto` as a safety net.
- **Affected breakpoints**: 320 / 375 / 768 / 1024

#### UI-003: Sprint risks page hardcodes `grid-cols-[1fr_320px]`
- **File(s)**: `frontend/src/app/projects/[id]/sprints/risks/page.tsx:181`
- **Category**: responsive
- **Issue**: Two-column layout without a breakpoint guard. Under 768 px the 320 px sidebar consumes ~60% of the viewport, squeezing the risk register cards to ~150 px wide.
- **User impact**: Risk titles wrap aggressively; severity chips overlap progress dots.
- **Fix**: `grid-cols-1 xl:grid-cols-[1fr_320px]`. Same anti-pattern likely repeats on sprint board's right-side detail panel (`xl:col-span-3` on `board/page.tsx:230`) — that one is guarded but verify on dependencies/mapping pages.
- **Affected breakpoints**: 320 / 375 / 768 / 1024

### HIGH

#### UI-004: Five admin tiles link to routes that don't exist
- **File(s)**: `frontend/src/app/admin/page.tsx:20-31`. Missing pages: `/admin/roles`, `/admin/connectors`, `/admin/custom-connectors`, `/admin/notifications`, `/admin/import-export`.
- **Category**: navigation / IA
- **Issue**: 5 of 10 quick-access tiles 404. No global `app/not-found.tsx` to soften the landing.
- **User impact**: Admin loses confidence in the surface; standard "Roles" click yields a blank page.
- **Fix**: Either remove the tiles until pages ship, gate them with a "Coming soon" badge that doesn't navigate, or stand up minimal stubs like `/files`, `/reports`, `/plugins` already do. Add `app/not-found.tsx`.

#### UI-005: No `loading.tsx`, `error.tsx`, `not-found.tsx` anywhere
- **File(s)**: tree-wide — `Glob frontend/src/app/**/{loading,error,not-found}.tsx` returns zero files.
- **Category**: states
- **Issue**: Per-page client `LoadingState`/`ErrorBanner` is used inconsistently. There is no route-level fallback while the bundle/initial fetch is pending, and unhandled render errors crash to the framework default screen.
- **User impact**: First paint on slow networks is blank; runtime exceptions wipe the whole shell.
- **Fix**: Add `app/loading.tsx` with the existing `<LoadingState>`, `app/error.tsx` that wraps `ErrorBanner` + Reset, and `app/not-found.tsx` for unmapped routes.

#### UI-006: `PageHero` padding is unresponsive
- **File(s)**: `frontend/src/components/layout/PageHero.tsx:33` (`px-10 pt-8 pb-6`); main body padding in `AppShell.tsx:73` is `px-4 sm:px-6 lg:px-10`.
- **Category**: responsive / consistency
- **Issue**: Hero sits inside `<main>` but has its own 40 px horizontal padding regardless of viewport. Below 1024 px it visibly bleeds 16 px past the body's inner padding edge.
- **User impact**: Misalignment between the page title block and the content cards on tablet and phone.
- **Fix**: Match the shell: `px-4 sm:px-6 lg:px-10`.
- **Affected breakpoints**: 320 / 375 / 768

#### UI-007: Dashboard chart rows are `grid-cols-3` with no breakpoint
- **File(s)**: `frontend/src/app/dashboard/page.tsx:195,259,427`
- **Category**: responsive
- **Issue**: Three rows of charts force 3 columns at every width. Under `md` they shrink to ~120 px; the `AreaChart width={760}` (line 224) and `Donut size={132}` are not responsive — they render with internal scroll or get visually clipped.
- **User impact**: Charts unreadable on tablets and phones.
- **Fix**: `grid-cols-1 lg:grid-cols-3`; make `AreaChart` accept a `width="100%"` viewBox or wrap in a `ResizeObserver` container.
- **Affected breakpoints**: 375 / 768 / 1024

#### UI-008: Two free-text inputs have no accessible label and no focus indicator
- **File(s)**:
  - `frontend/src/app/developer-workspace/page.tsx:790-794` (artifact-tree search)
  - `frontend/src/app/developer-workspace/page.tsx:691-694` (other search in left rail — same file, different region)
- **Category**: a11y
- **Issue**: `<input placeholder="Search files…" className="bg-transparent border-0 outline-none ..." />` — `outline-none` with no `focus-ring` paired class and no `<label htmlFor>` / `aria-label`. Placeholder text is not an accessible name (axe-rule wcag2a/label).
- **User impact**: Screen-reader users hear "edit"; keyboard users see no focus ring. Both fail WCAG 2.4.7 + 4.1.2.
- **Fix**: Wrap in `<label className="sr-only">Search files</label>` (or add `aria-label="Search files"`) and append the `focus-ring` utility (already defined in `globals.css:151`).

#### UI-009: Icon-only action buttons missing `aria-label`
- **File(s)**: `frontend/src/app/projects/page.tsx:168-170` and `frontend/src/app/agents/page.tsx:278` (both `<Button variant="ghost" size="icon"><MoreHorizontal /></Button>`).
- **Category**: a11y
- **Issue**: 32×32 px ghost buttons containing only a Lucide icon. No `aria-label`, no `<span class="sr-only">`. Lucide icons render without text content. Screen readers announce "button".
- **User impact**: Function unknown to AT users; fails WCAG 4.1.2.
- **Fix**: `<Button aria-label="More actions" variant="ghost" size="icon">…</Button>` consistently. Audit all `size="icon"` instances — grep returned 2; add to lint rule.

#### UI-010: Connector search input lacks `focus-ring` (and uses inline `outlineColor` on the wrapping `<label>` only)
- **File(s)**: `frontend/src/app/connectors/page.tsx:1090-1097`
- **Category**: a11y
- **Issue**: `className="bg-transparent border-0 outline-none w-full text-ink"` — no `focus-ring`. The wrapping `<label>` sets `outlineColor` inline (lines 1080-1081) but `<label>` does not receive focus.
- **User impact**: No visible focus state. WCAG 2.4.7 fail.
- **Fix**: Add `focus-ring` to the input class.

#### UI-011: Reconciliation page never fetches; primary button is a no-op
- **File(s)**: `frontend/src/app/reconciliation/page.tsx:28-43`
- **Category**: states
- **Issue**: `const reconRuns: ReconRun[] = []` is hardcoded; the "Run Reconciliation" button has no `onClick`. No loading state because there's no fetch; no error path; metrics show literal `"0%"` strings (`MetricCard label="Reconciliation Score" value="0%"`).
- **User impact**: Users believe recon is "working with 0% score" rather than "not wired"; clicking the primary CTA does nothing.
- **Fix**: Either render an `EmptyState` ("Reconciliation API not yet enabled — see Settings → Recon") + disabled CTA, or wire to `/api/v1/recon/runs`.

#### UI-012: Validation page renders demo data alongside real org stats with no clear distinction
- **File(s)**: `frontend/src/app/validation/page.tsx:131-156,172-179`
- **Category**: states / trust
- **Issue**: A `DemoBanner` appears, but below it the `summary` cells, `VALIDATION_CHECKS` rows, and `TYPE_BREAKDOWN` panels are entirely fabricated (e.g. "VC-9241 GL_LEDGER row count · passed · Priya Shah") regardless of backend state. The "OVERALL PASS RATE" sometimes shows real value, sometimes 92.4%; the rest doesn't switch.
- **User impact**: Operators may believe a fake user "owns" a fake rule; demo and real are interleaved.
- **Fix**: Gate the demo rows behind `if (hasProjects === false)` or replace with `EmptyState` when no real validation rules exist.

#### UI-013: Sprint timeline SVG width pinned at 1100 px
- **File(s)**: `frontend/src/app/projects/[id]/sprints/timeline/page.tsx:35-42`
- **Category**: responsive
- **Issue**: `CHART_WIDTH = 1100`, `LABEL_COL_WIDTH = 200` hardcoded. Without an `overflow-x-auto` wrapper or `viewBox`-based scaling, the SVG either overflows the viewport (causing body horizontal scroll) or gets visually clipped.
- **User impact**: Below 1100 px the timeline gets cut off or pushes the entire `<main>` horizontally.
- **Fix**: Render the SVG with `viewBox="0 0 1100 …"` and `width="100%"`, or wrap it in `<div className="overflow-x-auto">` so only the chart scrolls.
- **Affected breakpoints**: 320 / 375 / 768 / 1024

#### UI-014: `Card.title` renders as `<div>`, breaks heading hierarchy
- **File(s)**: `frontend/src/components/ui/Card.tsx:57-61`. `PageHero` already uses `<h1>` (`PageHero.tsx:60`); `CardSection` uses `<h2>` (`Card.tsx:97`).
- **Category**: a11y
- **Issue**: Most dashboards lay out `Card`-after-`Card` under one `<h1>`. Because `Card.title` is `<div className="text-[14px] font-semibold">`, the page has zero `<h2>` landmarks — only h1, then text. WCAG 1.3.1 / 2.4.10.
- **User impact**: SR users cannot jump card-to-card with heading nav.
- **Fix**: Change `Card.title` markup to `<h2 className="text-[14px] font-semibold ...">` (or accept an optional `headingLevel` prop).

#### UI-015: Tables widen beyond viewport but several lack the standard `overflow-x-auto` wrapper
- **File(s)**: `frontend/src/app/admin/users/page.tsx:49` (`<table className="w-full text-[13px] border-t border-hx">` — no overflow wrapper), `frontend/src/app/admin/system-health/page.tsx:54` (same).
- **Category**: responsive
- **Issue**: Tables have 5–7 columns without horizontal scroll. On narrow screens cells will compress and Avatar+email column will wrap awkwardly; `formatDate` and the Mail email line both push width.
- **User impact**: Either horizontal page scroll or cramped cells.
- **Fix**: Wrap each `<table>` in `<div className="overflow-x-auto">` (pattern already standard in `dashboard/page.tsx:351` and `projects/page.tsx:195`). The shared `.table-scroll` utility already exists in `globals.css:155` — use it.

#### UI-016: Inline-style page styling diverges from the token system
- **File(s)**: `frontend/src/app/developer-workspace/page.tsx` (hundreds of `style={{ padding: "8px 16px", fontSize: 11.5, ... }}` over lines 175-870), `frontend/src/app/setup/first-admin/page.tsx:1195` & similar, parts of `frontend/src/app/connectors/page.tsx:1080-1098`, `frontend/src/app/approval/page.tsx:31-95`.
- **Category**: consistency
- **Issue**: Inline pixel-style props bypass `--tweak-font-size` (`globals.css:58`), the density multiplier, theme tokens, and dark mode. Edits don't propagate via the Tailwind config.
- **User impact**: User tweaks (font size, dark mode) don't apply to these regions; visual drift over time.
- **Fix**: Replace inline pixel literals with the existing Tailwind utilities (`text-xs`, `px-3.5`, etc.) and CSS vars (`var(--con-line)`). Adopt as a lint rule going forward.

#### UI-017: Reconciliation page uses raw Tailwind palette instead of token aliases
- **File(s)**: `frontend/src/app/reconciliation/page.tsx:45` (`bg-amber-50 border-amber-200 text-amber-800`), `:83` (`bg-zinc-50/70`), `:105-106` (`text-amber-700 text-emerald-700`).
- **Category**: consistency
- **Issue**: Raw color palette instead of `bg-warn-soft` / `text-warn` / `bg-app-2` / `text-ok` that the rest of the app uses.
- **User impact**: Page won't track theme tweaks (brand color override, dark mode); color drift vs `Chip tone="warn"`.
- **Fix**: Swap to token classes: `bg-warn-soft text-warn` and `bg-app-2`.

### MEDIUM

#### UI-018: `divide-x divide-[var(--con-line)]` divider does not collapse with the grid
- **File(s)**: `frontend/src/app/dashboard/page.tsx:149,175`, `frontend/src/app/projects/page.tsx:132`
- **Category**: visual
- **Issue**: When the surrounding `grid-cols-5/6` reflows (after UI-001 fix), the `divide-x` lines remain horizontal-only and look broken on wrapped rows. Today they're hidden by the lack of reflow; after fix they need `divide-y divide-x lg:divide-x lg:divide-y-0`.
- **Fix**: Switch to `border` on individual `MetricCell` children, or replace `divide-x` with `gap-px bg-[var(--con-line)]` faux-border trick that survives wrapping.

#### UI-019: `Avatar size="md"` mixed with numeric `size={20}` — no consistent scale
- **File(s)**: `frontend/src/app/admin/users/page.tsx:64` uses `size="md"`; `dashboard/page.tsx:392` and `projects/page.tsx:281` use `size={20}`.
- **Category**: consistency
- **Issue**: Two Avatar APIs in use; the `"md"` keyword path lives in Users, numeric path elsewhere.
- **Fix**: Pick one (numeric is more flexible) and migrate; or expose both via prop union but document.

#### UI-020: First-admin wizard step content uses `outline-none` on textarea + select with `focus-ring` immediately after — duplicated pattern with raw `outline-none`
- **File(s)**: `frontend/src/app/setup/first-admin/page.tsx:1195,1349,1368`
- **Category**: a11y
- **Issue**: `outline-none focus-ring` is fine (focus-ring uses focus-visible). It's safe but undisciplined — `focus-ring` already includes `focus:outline-none`. Risk: someone copies the pattern and drops `focus-ring`.
- **Fix**: Remove the explicit `outline-none` because `focus-ring` already declares `focus:outline-none`. Document this in the component README.

#### UI-021: Bell, "Ask Helix", and "Search…" sidebar trigger lack keyboard shortcut wiring
- **File(s)**: `frontend/src/components/layout/Topbar.tsx:59-73`, `frontend/src/components/layout/Sidebar.tsx:136-147`
- **Category**: form UX / navigation
- **Issue**: Both controls advertise shortcuts (`⌘ K`, `⌘ J` Kbd hints) but neither button is wired to a keydown listener anywhere. Bell button is a no-op.
- **User impact**: User presses ⌘K, nothing happens; expectation mismatch.
- **Fix**: Implement the global `cmd+k` / `cmd+j` palette/ask shortcut, or hide the `<Kbd>` until wired.

#### UI-022: Tabs counts use `text-ink-4` (≈4.55:1) which is borderline for 10.5 px text
- **File(s)**: `frontend/src/components/ui/Tabs.tsx:91-93,131-133`
- **Category**: a11y
- **Issue**: `text-[10.5px]` tab counts use `text-ink-4`. Contrast meets AA for 14 px+ text but is borderline for 10.5 px (which AA treats as small text; needs 4.5:1, met just barely, but visual perception at that size is worse). Color comment in `tailwind.config.ts:64` notes "decorative use is fine at the prior shade" but counts are informational.
- **Fix**: Bump to `text-ink-3` (7.2:1) for counts.

#### UI-023: Mobile drawer sidebar overlay backdrop is a `<button>` but does not visibly indicate it
- **File(s)**: `frontend/src/components/layout/Sidebar.tsx:251-257`
- **Category**: a11y / consistency
- **Issue**: The backdrop is technically a `<button aria-label="Close navigation" tabIndex={-1}>` which is good. But its `aria-label` is identical to the explicit X button (line 205-209) — SRs may announce two "Close navigation" controls.
- **Fix**: Either move the dismiss role to a `<div role="presentation">` paired with a `keydown` Escape handler (already added in `useEffect` line 184), or differentiate labels ("Dismiss overlay" vs "Close navigation").

#### UI-024: First-admin wizard breaks if user reloads in the middle
- **File(s)**: `frontend/src/app/setup/first-admin/page.tsx` (whole file holds step state in component-local `useState`)
- **Category**: form UX / states
- **Issue**: No persistence; refreshing on step 3 sends user back to step 0 but token from step 0 lives in localStorage, leaving a half-provisioned org.
- **User impact**: Half-broken onboarding on accidental refresh.
- **Fix**: Persist the current step + form draft to `sessionStorage`; offer "Resume setup" CTA on `/setup/first-admin` if a draft exists.

#### UI-025: `MetricCell big` numbers don't truncate on narrow cells
- **File(s)**: `frontend/src/app/dashboard/page.tsx:149-172` (and many others)
- **Category**: visual
- **Issue**: After UI-001 fix, the cells will be ~150 px wide. The big number `font-mono` can still overflow without `truncate` or `text-ellipsis`. Will manifest as visual bug when fix lands.
- **Fix**: Add `truncate` + `min-w-0` to `MetricCell` value spans, or use `title={value}` for hover tooltip.

#### UI-026: Search inputs across the app vary in size and shape
- **File(s)**: Project search `projects/page.tsx:142-150` (h-8 rounded-[7px] pl-8), Knowledge `useId`-wired pattern (`knowledge/page.tsx`), Connectors uses inline `style={{ height }}` (`connectors/page.tsx:1075-1097`), Workspace search bypasses both (`developer-workspace/page.tsx:782-795`).
- **Category**: consistency
- **Issue**: No shared `<SearchInput>` primitive. Four+ different visual treatments.
- **Fix**: Extract `components/ui/SearchInput.tsx` with `aria-label`, `focus-ring`, leading icon slot.

#### UI-027: Modals do not preserve scroll position when closed/reopened
- **File(s)**: `frontend/src/components/ui/Modal.tsx` + `ConfirmModal.tsx`
- **Category**: form UX
- **Issue**: Body scroll is locked by `useFocusTrap`. After close, scroll is restored. But on long forms (NewTaskModal at `sprints/board/page.tsx:456+`) there is no internal scroll cap — modal will overflow viewport on mobile (`max-w-md` only constrains width).
- **Fix**: Add `max-h-[85vh] overflow-y-auto` to the Modal content container.

#### UI-028: Tabs and filter bar collide on `/projects` at narrow widths
- **File(s)**: `frontend/src/app/projects/page.tsx:142-171`
- **Category**: responsive
- **Issue**: Filter bar `flex items-center gap-3` has a 400 px search input + 6-tab Tabs + filter button + ghost icon button. No `flex-wrap`; below ~900 px controls overflow horizontally and clip.
- **Fix**: Add `flex-wrap gap-y-2` and let the 6-tab Tabs scroll horizontally with `overflow-x-auto`.

#### UI-029: `Project owner` chip on board task panel hardcodes `text-[10.5px]` "AGENT" suffix
- **File(s)**: `frontend/src/app/projects/[id]/sprints/board/page.tsx:326-327`
- **Category**: low-contrast / consistency
- **Issue**: "AGENT" label uses `text-ink-4` at 10.5 px — borderline AA. Identical pattern as UI-022.
- **Fix**: `text-ink-3` or upgrade to a real `Chip` tone.

#### UI-030: `WorkspaceSwitcher` button claims dropdown but has no menu
- **File(s)**: `frontend/src/components/layout/Sidebar.tsx:115-134`
- **Category**: form UX
- **Issue**: Renders ChevronDown, looks clickable, has no `onClick`/`aria-haspopup`. Same applies to `UserFooter` (line 149-163).
- **User impact**: User clicks expecting org switcher; nothing happens.
- **Fix**: Either wire to a real `Popover` or add `disabled` + `cursor-default` until the feature ships. Add `aria-haspopup="menu"` when real menu is added.

#### UI-031: Hero metric cells use `text-[28px]` / `text-[56px]` (validation hero) without `clamp`
- **File(s)**: `frontend/src/app/validation/page.tsx:185-188`
- **Category**: responsive
- **Issue**: `text-[56px]` pass-rate number does not shrink on narrow viewports. With the `1fr 1.4fr` grid it gets squeezed and overflows its parent.
- **Fix**: Use `clamp(32px, 6vw, 56px)` via inline style, or set a `sm:text-[40px] lg:text-[56px]` step.

#### UI-032: Touch targets in dense tables (24×24 px chevrons / 20×20 avatars) below 44 px
- **File(s)**: `frontend/src/app/projects/page.tsx:289-292` (`ArrowUpRight h-3.5 w-3.5` link as the entire row action), `dashboard/page.tsx:392` (Avatar size 20)
- **Category**: a11y / touch
- **Issue**: Apple HIG / WCAG 2.5.5 recommends 44×44 (or AAA 2.5.5). A `h-3.5 w-3.5` icon link is ≈14 px. The row itself is clickable too, but the icon as a discrete affordance is a touch hazard.
- **Fix**: Pad the link area: `<Link className="inline-flex items-center justify-center h-9 w-9">`. Avatar can stay small but its hover/click should target the row, not the avatar itself.

#### UI-033: `text-[10.5px]` "VC-9241" IDs and timestamps used in dashboard/projects/agents tables
- **File(s)**: `dashboard/page.tsx:251,285,381,417`; `projects/page.tsx:251` (`text-[10.5px] text-ink-4`)
- **Category**: a11y / readability
- **Issue**: 10.5 px is below the conventional 12 px floor for body text; even with `text-ink-4` at 4.55:1, perception suffers.
- **Fix**: Promote IDs to 11.5 px or display them in a tooltip rather than always-visible meta.

#### UI-034: New Project page doesn't disable Cancel link while submitting
- **File(s)**: `frontend/src/app/projects/new/page.tsx:130-135`
- **Category**: form UX
- **Issue**: While the POST is in-flight (`loading=true`), the Cancel `<Link>` can be clicked → navigation, race with the API callback.
- **Fix**: Render Cancel as `<Button>` disabled while loading.

#### UI-035: Approval mock page is purely decorative and indistinguishable from a real screen
- **File(s)**: `frontend/src/app/approval/page.tsx:28-95`
- **Category**: states / trust
- **Issue**: The page renders a blurred/non-blurred mock with hardcoded "Avery Johnson · P-1042" data. No banner, no demo flag.
- **User impact**: A user landing here from the sidebar (if added) believes a real approval is pending.
- **Fix**: Add the same `<DemoBanner>` pattern as `/dashboard`.

### LOW

#### UI-036: `Forgot?` link on login uses `href="#"` (dead link)
- **File(s)**: `frontend/src/app/login/page.tsx:83-85`
- **Category**: navigation / IA
- **Fix**: Either implement reset flow or remove the link.

#### UI-037: Heavy client bundles on `/dashboard` (every chart + 9+ icon families)
- **File(s)**: `dashboard/page.tsx:11-35` imports `AreaChart`, `Donut`, `Sparkline`, `MetricCell`, `Card`, `Tabs`, `Chip`, `DemoBanner`, `Avatar`, `Button`, `ProgressBar`, `StatusBadge`, `ErrorBanner`, plus 3 icon sets.
- **Category**: lighthouse / perf
- **Fix**: `next/dynamic` the chart components (`AreaChart`, `Donut`) and gate behind `ssr: false`; tree-shake unused Lucide icons.

#### UI-038: External font loaded via `@import` in CSS instead of Next `next/font`
- **File(s)**: `frontend/src/app/globals.css:1` (`@import url("https://fonts.googleapis.com/...")`)
- **Category**: lighthouse / perf
- **Issue**: Render-blocking. `next/font` would self-host and inline CSS, eliminating the network round-trip.
- **Fix**: Migrate to `next/font/google` for Geist + Geist Mono.

#### UI-039: No `<meta viewport>` in `frontend/src/app/layout.tsx`
- **File(s)**: `frontend/src/app/layout.tsx:5-9`
- **Category**: lighthouse
- **Issue**: Next 14 injects a default viewport, but app exports no `Viewport` config to override scale. Default is fine for now; flag only for awareness.
- **Fix**: Add `export const viewport: Viewport = { width: "device-width", initialScale: 1 };` to surface intent and prevent silent regressions.

#### UI-040: Hardcoded dates / numbers ("© 2026", "12:42:08") render literally — no i18n hook
- **File(s)**: `login/page.tsx:46`, `dashboard/page.tsx:52-62`
- **Category**: i18n readiness
- **Issue**: There is no `next-intl` or i18n system, so this is not a current bug. Flagging because `Intl.DateTimeFormat` is used in places (`projects/page.tsx:344-357`) but a string like `"2m ago"` is computed in English regardless of locale.
- **Fix**: Centralize relative-time formatting; consider `Intl.RelativeTimeFormat`.

#### UI-041: Sidebar "All systems operational" indicator is hardcoded green dot
- **File(s)**: `frontend/src/components/layout/Sidebar.tsx:228-231`
- **Category**: trust / states
- **Issue**: Always green regardless of actual system health.
- **Fix**: Bind to `/api/v1/system/health` summary.

#### UI-042: Stub pages all link "Back to Dashboard" with no breadcrumb context
- **File(s)**: `files`, `reports`, `templates`, `plugins` (`files/page.tsx:30-32` etc.)
- **Category**: navigation
- **Issue**: After landing on a coming-soon page, only path back is dashboard. No status timeline or roadmap link.
- **Fix**: Add "Track on GitHub" link to the relevant issue/milestone.

#### UI-043: `Chip dot` and `Chip dot pulse` mixed without clear semantic rules
- **File(s)**: `dashboard/page.tsx:266` (`<Chip tone="ok" dot pulse>Live</Chip>`), `StatusBadge.tsx:52` (`pulse={!!entry.pulse}`)
- **Category**: consistency / low
- **Issue**: Pulse animation also fires on `in_progress` and `active` (StatusBadge map). Three or four pulses on one screen creates visual noise.
- **Fix**: Reserve pulse for actively-running workflows only; static dot for "live but idle".

#### UI-044: `formatDate` / `formatTime` / `formatNumber` defined in `lib/utils` but not used uniformly
- **File(s)**: `reconciliation/page.tsx:108`, but `projects/page.tsx:344-357` defines its own `formatRelative` inline.
- **Category**: consistency
- **Fix**: Centralize all date formatting in `lib/utils.ts`; expose `formatRelative`, `formatRelativeShort`.

#### UI-045: `text-amber-700` / `text-emerald-700` hard-coded for table cell numbers
- **File(s)**: `reconciliation/page.tsx:105-106`
- **Category**: consistency (sub-case of UI-017)
- **Fix**: Use `text-warn` / `text-ok` token classes.

#### UI-046: No skeleton component — `LoadingState` is a spinner only
- **File(s)**: `components/ui/LoadingState.tsx`
- **Category**: states / polish
- **Issue**: Spinner-only loading on data-heavy pages (`projects`, `dashboard`) causes visible layout shift when data arrives. A skeleton matching the final shape would reduce CLS.
- **Fix**: Add a `<Skeleton>` primitive (e.g. for table rows, metric cells); use on the first paint of dashboard + projects.

## Lighthouse blockers (static analysis)

- **Render-blocking font import** (UI-038). Replace with `next/font`.
- **Charts in client bundle on every dashboard load** (UI-037). Lazy-load AreaChart / Donut / Sparkline.
- **No `<meta viewport>` override** (UI-039) — non-blocker but worth declaring explicitly.
- **Open redirects** none observed; CSP defined on the marketing site (`website/index.html:16`) but **not on the Next app** — no `next.config` headers configured. Recommend a strict CSP for the production build.
- **Heading hierarchy** (UI-014): every dashboard has exactly one `<h1>` and zero `<h2>`. Lighthouse a11y will flag.
- **Icon-only buttons missing labels** (UI-009): axe-core will flag.
- **Two anonymous text inputs in dev-workspace** (UI-008): axe-core will flag.
- **Color contrast on `text-ink-4` 10.5 px text** (UI-022, UI-033): Lighthouse contrast checker may report borderline failures depending on background variance.
- **No `loading.tsx` / `error.tsx`** (UI-005): Web Vitals will include any uncaught-error retries in TBT/LCP.

What's NOT broken (kept for context):
- Modal primitive is properly accessible (`Modal.tsx:38-102`): `role="dialog"`, `aria-modal`, `aria-labelledby`, focus trap, Escape close, return-focus, body-scroll lock.
- ConfirmModal moves focus to Cancel (`ConfirmModal.tsx:43-48`) — protects against accidental destructive Enter.
- `Tabs` implements full WAI-ARIA APG tab pattern with arrow-key / Home / End navigation and roving tabindex (`Tabs.tsx:36-138`).
- `Sidebar` has an accessible mobile drawer with body-scroll lock + Escape handler (`Sidebar.tsx:179-191`).
- `SprintKanbanBoard` ships dnd-kit keyboard sensor + live-region announcements (`SprintKanbanBoard.tsx:75-125`).
- `AppShell` includes a skip-to-main link (`AppShell.tsx:46-51`) — first focusable element on every page.
- Tokens (`globals.css:34-56`) include WCAG-AA-tuned ink scale with documented contrast ratios (`tailwind.config.ts:60-74`).
- `prefers-reduced-motion` honored globally (`globals.css:197-210`).
- Marketing site has solid SEO meta + JSON-LD + CSP (`website/index.html`).
- Sprint board NewTaskModal uses `useId`, `<label htmlFor>`, and `aria-required` correctly (`sprints/board/page.tsx:546-560`).
