# Frontend Verification — UI MEDIUM/LOW + M-017

Read-only confirmation of which `docs/review-v5/ui-ux-review.md` findings actually landed
on branch `upgrade/review-and-fix` (frontend cleanup agent crashed before reporting).
Method: opened each cited file under `frontend/src/` and checked for the intended fix.

## UI MEDIUM

| Finding | Status | Evidence |
|---|---|---|
| UI-018 divider reflow (dashboard/projects strips) | DONE | `dashboard/page.tsx:169` & `projects/page.tsx:133` now `divide-y lg:divide-y-0 lg:divide-x divide-[var(--con-line)]` — dividers survive wrap. LLM-spend strip `dashboard:196` too. |
| UI-019 Avatar size API unified | DONE | All 3 cited sites numeric: `admin/users:65` `size={24}`, `dashboard:415` `size={20}`, `projects:285` `size={20}`. (Avatar still accepts keyword union but no caller uses `"md"`.) |
| UI-020 redundant outline-none removed (first-admin) | DONE | first-admin Input/Select/textarea use `focus-ring` with NO explicit `outline-none` (`page.tsx:1271,1425,1444`). |
| UI-021 ⌘K/⌘J wired or Kbd hidden; Bell handled | DONE | Topbar drops the Bell + ⌘J Kbd hint entirely (`Topbar.tsx:58-68`). Sidebar `SearchTrigger` is `disabled` w/ no ⌘K Kbd (`Sidebar.tsx:133-149`). (Nav 1-6 hover Kbd remain — those are route shortcuts, out of scope.) |
| UI-022 Tabs counts text-ink-3 | DONE | Both count spans `text-ink-3` (`Tabs.tsx:92,132`); also size is now `text-[11px]` not 10.5px. |
| UI-023 sidebar backdrop label differentiated | DONE | Backdrop `aria-label="Dismiss navigation overlay"` vs X button `"Close navigation"` (`Sidebar.tsx:302-307` vs `258`). |
| UI-024 first-admin draft → sessionStorage | DONE | `DRAFT_KEY` save/restore effects strip secrets; cleared on finish (`first-admin/page.tsx:241-287,543`). |
| UI-025 metric value truncate min-w-0 | DONE | `MetricCell` wrapper `min-w-0`, value line `truncate` + `title` (`MetricCard.tsx:103,108`). |
| UI-026 shared SearchInput across projects/knowledge/connectors/dev-workspace | **PARTIAL** | `SearchInput` primitive exists and is used in `projects:145`, `connectors:1063`, `developer-workspace:596` — but `knowledge/page.tsx:123` still renders a raw `<input placeholder="Search uploaded docs…">`, not the primitive. |
| UI-027 Modal max-h-[85vh] overflow-y-auto | DONE | Modal content container `max-h-[85vh] overflow-y-auto` (`Modal.tsx:82`). |
| UI-028 projects filter bar flex-wrap | DONE | Filter bar `flex flex-wrap ... gap-y-2`, tabs wrapped in `overflow-x-auto` (`projects/page.tsx:144,152`). |
| UI-029 board AGENT chip text-ink-3 | **MISSING** | "AGENT" suffix still `text-[10.5px] text-ink-4` (`projects/[id]/sprints/board/page.tsx:327`) — not bumped to `text-ink-3`. |
| UI-030 WorkspaceSwitcher/UserFooter disabled affordance | DONE | Both ChevronDowns removed; `WorkspaceSwitcher` is a static `<div>`, `UserFooter` has no menu chevron (`Sidebar.tsx:114-131,202-216`). |
| UI-031 validation hero clamp | DONE | Hero stepped `text-[40px] sm:text-[48px] lg:text-[56px] ... truncate` (`validation/page.tsx:188`) — the breakpoint-step alternative from the fix. |
| UI-032 dense-table touch targets ≥44px | DONE | Projects row action now `inline-flex ... h-9 w-9` link (`projects/page.tsx:297`). Dashboard avatar stays decorative inside a fully-clickable row (as the fix allowed). |
| UI-033 10.5px IDs bumped | DONE | Cited IDs/timestamps now ≥11px: dashboard P-1042 `text-[11px]` (`dashboard:404`), updated `text-[11.5px]` (`:440`); projects ID `text-[11px]` (`:255`). (Remaining 10.5px in dashboard:381/459 are uppercase table-header eyebrows, not the cited IDs.) |
| UI-034 new-project Cancel disabled while submitting | DONE | Header Cancel renders as disabled `<Button>` when `loading` instead of a live `<Link>` (`projects/new/page.tsx:130-144`). |
| UI-035 approval page DemoBanner | DONE | `<DemoBanner>` rendered at top of page (`approval/page.tsx:584`, imported `:7`). |

## UI LOW

| Finding | Status | Evidence |
|---|---|---|
| UI-036 login Forgot link | DONE | Dead `href="#"` link removed; only the Password label remains (`login/page.tsx:79-85`). |
| UI-037 next/dynamic charts on dashboard | DONE | `AreaChart`/`Donut`/`Sparkline` lazy-loaded via `next/dynamic` with `ssr:false` + Skeleton fallback (`dashboard/page.tsx:39-50`). |
| UI-038 next/font instead of CSS @import | DONE* | Render-blocking `@import` removed from `globals.css:1`; Geist now loaded via `<link>`+preconnect in `layout.tsx:26-33`. *Implemented as `<link>` not literal `next/font` (documented: Geist absent from next/font for pinned Next 14.2.35, no new deps). Core issue (blocking @import) resolved. |
| UI-039 viewport export in layout.tsx | DONE | `export const viewport: Viewport = { width:"device-width", initialScale:1 }` (`layout.tsx:13-16`). |
| UI-040/044 centralised relative-time in lib/utils | DONE | `formatRelative` added to `lib/utils.ts:33-46`; `projects/page.tsx:37,354-357` delegates to it (inline variant removed). |
| UI-041 sidebar health dot bound to API | DONE | `SystemStatus` fetches `/api/v1/system/health`, drives dot color + label, falls back to "Status unknown" (`Sidebar.tsx:159-200`). |
| UI-042 stub pages roadmap link | DONE | "Track on GitHub" link present on all 4 stubs (files, reports, templates, plugins). |
| UI-043 pulse reserved for running | DONE | `StatusBadge` map sets `pulse:true` only on running/started/in_progress; `active` has no pulse (`StatusBadge.tsx:9-12`). |
| UI-045 reconciliation tokens | DONE | Raw amber/emerald palette replaced with `bg-warn-soft`/`text-warn`/`text-ok` (`reconciliation/page.tsx:51,111-112`). |
| UI-046 Skeleton primitive on dashboard/projects | DONE | `Skeleton`/`SkeletonMetricRow`/`SkeletonTable` exist (`ui/Skeleton.tsx`); used at `dashboard:167` and `projects:178`. |

## Code

| Finding | Status | Evidence |
|---|---|---|
| M-017 consolidate the two API clients | **PARTIAL** | Both files still exist. `lib/api/client.ts` (`apiGet`/`apiPost`) is marked `@deprecated` and has ZERO importers (grep finds only its own definitions). `lib/use-api.ts` (`useApi()`) is the live hook, imported by `lib/queries/projects.ts` + `lib/queries/llm-providers.ts`. Logic was de-duplicated (identical 204 guard + `detail`→status error envelope) but the dead module was NOT deleted. Note: most pages (dashboard, projects, admin/users, setup/first-admin) still call raw `fetch()` directly — not `useApi()` — so a third ad-hoc pattern remains app-wide, though that's outside M-017's two-client scope. |

---

## TO FINISH (MISSING / PARTIAL only)

- **UI-029 (MISSING)** — Bump the board task-panel "AGENT" suffix from `text-ink-4` to `text-ink-3` at `frontend/src/app/projects/[id]/sprints/board/page.tsx:327`.
- **UI-026 (PARTIAL)** — Migrate the Knowledge page search to the shared `SearchInput` primitive; it still uses a raw `<input placeholder="Search uploaded docs…">` at `frontend/src/app/knowledge/page.tsx:123` (projects/connectors/dev-workspace already adopted it).
- **M-017 (PARTIAL)** — Two API-client modules still coexist. `lib/api/client.ts` is deprecated with no importers (safe to delete) but was not removed; `lib/use-api.ts` is the live one. Decide: delete `client.ts` to truly consolidate. Separately, raw `fetch()` call sites across pages were not migrated to `useApi()`.
- **UI-038 (DONE, note)** — Resolved via `<link>`+preconnect rather than literal `next/font`, by design. Flag only if a strict "must use next/font" interpretation is required.
