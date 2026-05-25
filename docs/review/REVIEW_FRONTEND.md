# Frontend Code Review

> Generated 2026-05-26. Scope: `frontend/src/**`.

## 1. High-level architecture

Helix Migration's frontend is a **Next.js 14 App Router** TypeScript SPA (with `output: "standalone"`) that wraps the FastAPI backend in a multi-page operations console plus a marketing landing surface (`/`) and a multi-step onboarding wizard (`/setup/first-admin`).

```
src/
├── app/                          ← Next App Router (38 routes)
│   ├── layout.tsx                ← <html>/<body>, mounts <Providers>
│   ├── providers.tsx             ← QueryClient + AuthProvider + ThemeProvider
│   ├── page.tsx                  ← Marketing landing page (huge inline JSX)
│   ├── login/                    ← /login
│   ├── setup/first-admin/        ← 6-step org+admin+LLM+routing wizard
│   ├── dashboard/                ← Command center
│   ├── projects/                 ← list, new, [id], [id]/agents, [id]/developer-workspace
│   ├── projects/[id]/sprints/    ← 10 sub-routes (board, board, mapping, timeline, …)
│   ├── agents/                   ← global agents page (BMAD-pipeline view)
│   ├── developer-workspace/      ← three-pane IDE (no [id] uses mock data)
│   ├── developer-workspace/[id]/ ← real API-driven artifact reviewer
│   ├── validation/, reconciliation/, approval/
│   ├── connectors/               ← grid + 3-step modal
│   ├── settings/                 ← profile + tweaks + notifications
│   ├── files/, plugins/, reports/, templates/      ← placeholder stubs
│   └── admin/                    ← users, audit-logs, system-health,
│                                   agent-mapping, llm-settings
│
├── components/
│   ├── layout/                   ← AppShell, AdminShell, ProjectShell,
│   │                                Sidebar, Topbar, PageHero, HelixLogo
│   ├── ui/                       ← 17 atomic primitives (Button, Card, Chip,
│   │                                StatusBadge, MetricCard, Donut, AreaChart,
│   │                                Sparkline, Tabs, Avatar, EmptyState,
│   │                                LoadingState, ErrorBanner, Table, Kbd,
│   │                                ProgressBar)
│   ├── sprints/                  ← Sprint-domain components: primitives,
│   │                                charts, kanban (dnd-kit), React-Flow
│   │                                mapping canvas, custom MappingNode
│   ├── icons/                    ← AppIcon (simple-icons), AgentIcon
│   │                                (react-icons), LLMIcon
│   ├── website/                  ← WebsiteNav, WebsiteFooter (marketing)
│   ├── ThemeProvider.tsx         ← Mounts Zustand `useTweaks`, debounced
│   │                                /api/v1/users/me/preferences PATCH
│   ├── ThemeToggle.tsx           ← Legacy emoji-cycle button (orphan?)
│   ├── TweaksPanel.tsx           ← Drawer for runtime theme tweaks
│   └── ArtifactDiff.tsx          ← Naive line-diff display
│
├── features/developer-workspace/ ← Older diff/version/approval splinters
│
├── lib/
│   ├── auth-context.tsx          ← Context, login, setup-first-admin, logout
│   ├── use-api.ts                ← Typed wrapper around fetch w/ token
│   ├── api/client.ts             ← apiGet/apiPost convenience (legacy)
│   ├── query-client.ts           ← React-Query QueryClient (staleTime 30s)
│   ├── store.ts                  ← Zustand: activeProjectId, sidebarCollapsed
│   ├── theme-store.ts            ← Zustand: theme/density/font/color/tint
│   ├── theme.ts                  ← Legacy direct DOM-class helpers (orphan?)
│   ├── api-types.ts              ← Hand-maintained OpenAPI mirrors
│   ├── queries/                  ← React-Query hooks (only projects + llm)
│   ├── sprints/                  ← types + api adapters + barrel
│   └── utils.ts                  ← cn(), formatters, statusTone()
│
└── types/css.d.ts                ← `*.css` module declaration shim
```

**Data flow.** Most pages use a mixed pattern:

1. Pull `token` from `useAuth()` (React context).
2. Either fire a raw `fetch()` inside a `useEffect` (older pages) or use the React-Query hooks under `lib/queries/` (LLM + projects only).
3. Mutations go straight back through `fetch()`. Optimistic UI is only attempted on the kanban (`SprintKanbanBoard`) and approval (`/sprints/approval`) pages.

**State.** Zustand carries two stores: `useAppStore` (sidebar + activeProject — *currently unused by Sidebar/Topbar*) and `useTweaks` (theme). React Query carries server state for the **handful of pages migrated to it** (`projects`, `llm-providers`, `llm-providers/catalogue`, `llm-agent-mappings`). All sprint pages call `fetch*` helpers from `lib/sprints/api.ts` outside of React Query, so we have **two parallel server-state systems**.

**Auth.** The `helix_token` JWT is stored in `localStorage`, read once at mount, and threaded through `useAuth().token` to every fetcher. The SSE execution stream (`subscribeToExecutions`) **embeds the token in the URL query string** because EventSource can't set headers.

**Design tokens.** Tailwind + CSS-variable hybrid: `tailwind.config.ts` defines a `con-*` palette backed by `var(--con-*)`; the tweaks store rewrites those vars on the fly. Pages use a mix of token classes (`bg-surface`, `text-ink`, `border-hx`) and **hundreds of raw inline `style={{}}`** values with pixel literals (most painfully in `setup/first-admin`, `agents`, `connectors`, `developer-workspace`). The design vocabulary is consistent; the *expression* of it isn't.

---

## 2. File-by-file review

### frontend/tsconfig.json
**Purpose:** TypeScript config.
**Reviewed lines:** 23.

#### Issues
- 🟡 MED line 18: `"types": ["node"]` is unusually narrow — `@types/react` and `@types/react-dom` are listed as devDeps but won't be auto-injected, relying on Next's plugin (`@next/plugin-next`) at line 16 to inject them indirectly. Switching IDE/build chain (e.g. ESM module-graph tools) can produce surprising "Cannot find namespace 'JSX'" errors. Removing `"types"` entirely is the safer default.
- 🔵 LOW line 4: `"target": "ES2017"` is fine for browsers but `tailwind-merge` / `zustand` ship modern code already; bumping to ES2020 is a free 2-3% bundle reduction.
- 🔵 LOW: no `paths` for `@/components`, `@/lib` separately — single wildcard `@/*` is correct, but no `baseUrl` is set; Next's plugin fills this in. Fine.

### frontend/next.config.mjs
**Purpose:** Next.js build configuration.
**Reviewed lines:** 7.

#### Issues
- 🟡 MED line 3: `output: "standalone"` is set but **no `eslint.ignoreDuringBuilds` or `typescript.ignoreBuildErrors` knobs are present**. Combined with the strict-mode TS config, a single inconsistency surfaces as a hard build failure in the Dockerfile (`npm run build` line 14). Real-world ops would want a CI step that runs lint+tsc separately so the prod build step is deterministic.
- 🟡 MED: no `images.remotePatterns`, no `experimental.serverActions`, no `headers()` (e.g. CSP). All `localStorage` use is hostile-XSS-territory once the API base is exposed; CSP-default-src is a cheap mitigation.
- 🔵 LOW: missing `productionBrowserSourceMaps: false` is fine for OSS — but combined with auth-via-localStorage you might want to consider whether you ship source-maps in container images.

### frontend/Dockerfile
**Purpose:** Multi-stage build for the standalone server.
**Reviewed lines:** 24.

#### Issues
- 🟠 HIGH line 6: `RUN npm install --legacy-peer-deps` — `--legacy-peer-deps` masks real peer-dep failures. Migrate to `npm ci` once the lockfile is healthy, and audit which transitive deps require legacy resolution.
- 🟠 HIGH line 13: `COPY . .` will copy `Helix Figma Frontend/`, `e2e/`, `.next/`, `node_modules/`, `playwright.config.ts`. A `.dockerignore` is implied but if it's missing this slows builds + leaks files. Verify presence.
- 🟡 MED line 9-10: `ARG NEXT_PUBLIC_API_URL` is baked into the build via the env var. This means the same image cannot be reused across environments — each cluster needs its own image tag, defeating the typical "build once, run everywhere" container model. Switch to a runtime config (publicRuntimeConfig was deprecated; the modern fix is `window.__HELIX_CONFIG__` injected at HTML serving time).
- 🟡 MED line 16-22: the runner stage is missing `USER node` — server runs as root inside the container. Trivial hardening fix.
- 🔵 LOW line 23: no `HEALTHCHECK` instruction.

### frontend/tailwind.config.ts
**Purpose:** Tailwind theme + token mapping to CSS vars.
**Reviewed lines:** 115.

#### Issues
- 🔵 LOW line 8: `fontFamily.sans` listing both Geist and Inter is fine but neither font is actually `<link>`'ed from `app/layout.tsx` — relying on Geist being a Next default. If the project ever drops `next/font/google` defaults, the entire app falls back to system. Make this explicit via `import { GeistSans } from "geist/font/sans"` in `layout.tsx`.
- 🔵 LOW line 75-82: shadow `glow` and `glow-lg` are hard-coded RGBA from the indigo `helix-500`, not derived from `--con-brand` — runtime tweak of the primary color **does not** update the glow shadows. Cosmetic inconsistency.
- 🔵 LOW line 91-93: `backgroundImage.soft-indigo` is named after a brand color (indigo) yet hard-codes `#F5F3FF / #EEF0FF` — same de-token-ization risk if surface-tint is rebranded later.

### frontend/src/app/layout.tsx
**Purpose:** Root layout, hydrates Providers.
**Reviewed lines:** 19.

#### Issues
- 🟡 MED line 14: `<body className="bg-app text-ink antialiased">` references `bg-app` / `text-ink` utilities that aren't defined in tailwind config — they must be defined in `globals.css` (`@layer utilities`). If that file is ever pruned, every page silently loses its background. Worth promoting these to first-class Tailwind colors (or commenting the dependency).
- 🔵 LOW line 5: `Metadata` is global; missing `metadataBase`, `openGraph`, `twitter` so social cards will be inconsistent.

### frontend/src/app/providers.tsx
**Purpose:** Compose QueryClient, AuthProvider, ThemeProvider.
**Reviewed lines:** 16.

#### Issues
- None — clean composition.

#### Improvements / Optimizations / Suggestions
- Consider wrapping in `<Suspense>` boundary so the new React `use()` pattern can be adopted in pages.

### frontend/src/app/page.tsx
**Purpose:** Marketing landing page.
**Reviewed lines:** 593.

#### Issues
- 🟡 MED line 1-593: a single ~600-line file holds Hero, Features, Architecture, AgentFlow, Validation, DevWorkspace, Connectors, OSS, CTA + 5 inline helper components. Extract to `app/(marketing)/_components/*` so the public-facing marketing JSX can iterate without bloating the App Router barrel.
- 🟡 MED line 18-19: `WebsiteNav` and `WebsiteFooter` are `"use client"` (see their files) but this page is a server component. The nav/footer client boundary forces every nested icon import to traverse the client manifest. Fine, but inflates the marketing bundle by ~50 KB.
- 🟡 MED line 74-87: anchor links `href="https://github.com/datainteg/helix-ai-migration"` are inconsistent — some have `target="_blank" rel="noreferrer"`, others (e.g. "Read Docs" link line 81) don't. New-window external links should be uniform for `rel="noopener"` security.
- 🔵 LOW line 320-331: terminal mock uses `<div className="text-emerald-400">$ git clone…</div>` — copy-paste hostile. Wrap in `<pre>` with `tabular-nums` and an inline copy-to-clipboard button.
- 🔵 LOW line 442: `style={{ color: m.c }}` is inline CSS for a brand color literal — escapes the design token system. Map `"#6366F1"` etc. to `var(--con-brand)` etc.
- 🔵 LOW line 526-552: `AgentFlowDiagram` is purely decorative but uses individual `<div>` chips with hard-coded HEX backgrounds. Wraps to multiple lines on mobile (good) but the arrows render in odd positions. Replace with an SVG.

### frontend/src/app/login/page.tsx
**Purpose:** Email/password login.
**Reviewed lines:** 113.

#### Issues
- 🟠 HIGH line 50-63: After login, `setUser({ email, name: email.split("@")[0] })` constructs the user's name from the email local-part instead of waiting for `/auth/me`. If the user's actual name is "Avery Johnson" but they log in with `avery@datainteg.io`, the sidebar will say "avery" until refresh. Also leaks the email shape into the UI name field.
- 🟡 MED line 83: "Forgot?" link goes to `href="#"` — clicking it scrolls to top, breaking the form's perceived stability. Either implement the route or render an inactive `<span>`.
- 🟡 MED line 60: `localStorage.setItem("helix_token", data.access_token)` stores the JWT in localStorage. Per OWASP, JWTs in localStorage are XSS-exfiltratable. Move to an httpOnly cookie at the next backend pass.
- 🔵 LOW line 12-14: `useState("")` x3 + `loading` + `error` — would benefit from a `useReducer`-style shape or `react-hook-form`. Today's wins: free per-field-validation + free `disabled={!email || !password}` derivation.
- 🔵 LOW line 33-36: `<Link href="/">` wraps logo+wordmark with no `aria-label` — screen reader hears "Helix Migration link" (correct) but better to add `aria-label="Home"` to the link itself.
- 🔵 LOW line 75, 94: `focus-ring` utility is referenced. Ensure it lives in `globals.css`; otherwise this is a dead class.

#### Improvements
- Add Enter-to-submit confirmation, autofocus on the email field, `inputMode="email"` and `autoComplete="email" / "current-password"` for password manager UX.

### frontend/src/app/setup/first-admin/page.tsx
**Purpose:** 6-step onboarding wizard.
**Reviewed lines:** 1360.

#### Issues
- 🔴 CRITICAL line 250-284: the `useEffect` rebuilds the entire `data.agents` array on every render where `data.providers.map(...).join("|")` changes — but its dependency array uses **the join result as the only key**, with `eslint-disable-next-line` swallowing the warning. The effect calls `update("agents", ...)` which lives inside `data` — this is a self-referential update that **can re-fire** if any setter inside `update` is unstable. Today it's stable (functional `setData`), but adding any prop drilling breaks it. Replace with a `useMemo` of derived agents and a separate `useEffect` that only fires on provider-set changes.
- 🔴 CRITICAL line 329: `localStorage.setItem("helix_token", body.access_token);` inside `persistStep0` — the wizard short-circuits the AuthContext's `setupFirstAdmin` flow (which would auto-navigate). The token is written to storage but the AuthContext state still has `token === null` until next page refresh. **Step 1's `useEffect` for theme-sync may *not* fire** because `useAuth().token` doesn't update mid-wizard. Pages opened in another tab during this wizard will fail to hydrate. Reuse `setupFirstAdmin` from AuthContext (and add an opt-in to suppress its `router.push`).
- 🟠 HIGH line 76-87: `LLM_PROVIDERS` hard-codes provider models. These will drift from the backend `/llm-providers/catalogue` endpoint. Two sources of truth means a new model in the backend won't appear until somebody opens this file. Replace with a fetch to the catalogue endpoint at step-1 mount.
- 🟠 HIGH line 91-98: `BMAD_AGENTS.defaultModel` references models like `"claude-haiku-4-5"` and `"gpt-5.5"` that **don't exist yet** as of 2026-05-26 — these are speculative future model IDs. When the setup runs the resulting agent mapping POST might fail with "unknown model". Defer to backend catalogue defaults.
- 🟠 HIGH line 350: API key is passed empty (`api_key: p.apiKey || ""`) for keyless providers. The backend has to enforce that empty key is OK only for `bedrock/vertex/local`. If it doesn't, a misconfigured wizard run silently saves a useless provider. Send `null` (or omit the field) for keyless providers.
- 🟡 MED line 312-374: each step's persistence handler is a one-shot — there's **no transactional rollback**. If step 2 fails after step 1 created 3 providers, the wizard returns to step 2 with `providerIds` populated, but if the user *navigates back* to step 1 they can edit the form and the next "Save providers" click will conflict (the API will create duplicates). Persist immediately on each change or guard "save" with idempotency keys.
- 🟡 MED line 473: `stepValidity[step]` array index has no fallback; `step === 5` returns `true` correctly, but if a future step is added without extending the array the validator silently returns `undefined` (falsy, blocks). Use a `Record<number, boolean>` or `switch`.
- 🟡 MED line 552-557: `disabled={!canJump}` on a `<button>` is correct, but the rail offers no keyboard navigation between steps (no `aria-current="step"`). Wizards should be navigable with arrow keys, and announce the current step via `aria-current="step"`.
- 🟡 MED line 1314-1328: `Input` component is a function with `className` defaulted via concatenation rather than `cn()`. Combined with `disabled:bg-app-2` etc. it's hard to override. Reuse the shared `Button` pattern.
- 🟡 MED line 924-1041: `StepAgents` table renders 6 rows of `<Input type="number">` with no min/max guarding. Negative temperatures and `max_tokens=-1` are valid form input. Add `min="0"` and `min="1"` constraints (and visual error states).
- 🔵 LOW line 1170: `<Input value={`You · ${data.name || "First admin"}`} disabled />` — disabled inputs are not focusable, so the screen reader skips them entirely. Use a `<div role="textbox" aria-readonly>` or just a `<p>`.

#### Improvements
- Persist the partial wizard state (`data`, `persisted`, `step`) to `localStorage` so a closed tab can resume. Today, a refresh on step 3 sends the user back to step 0 with the workspace already provisioned.
- The `slugify` function should expose validation feedback ("slug `acme-prod` is already taken") — currently silent.
- `KEYLESS_PROVIDERS` Set is defined twice (here and `/admin/llm-settings/page.tsx` line 44) with slightly different members (`local` missing from admin). Centralize.

### frontend/src/app/dashboard/page.tsx
**Purpose:** Migration Command Center.
**Reviewed lines:** 438.

#### Issues
- 🔴 CRITICAL: **100% of the data on this page is hard-coded demo data** (lines 33-92). The page is shipped behind a real `<AppShell>` and looks production-ready; nothing tells the operator that the metrics are fictional. Add a banner / dev-only watermark, or hide the page until at least one widget is wired to the API.
- 🟠 HIGH line 95: `useState("30")` for `trendRange` — but `TREND_DATA` is a single 10-point array regardless of selection, so the tabs are decorative. This is misleading UX — switching ranges should fetch new data or fail honestly.
- 🟡 MED line 119: `grid-cols-5` is hard-coded — on a narrow viewport (<1024px) this becomes unreadable. Wrap with responsive `lg:grid-cols-5` and a stacked fallback.
- 🟡 MED line 285-356: table renders without keyboard focus management. The whole row is `cursor-pointer hover:bg-surface-hi` but the click target is a `<Link>` inside the title cell only. Clicking elsewhere on the row does nothing — but visually invites it. Either make the row clickable end-to-end (wrap row content in `<Link>`) or remove the hover affordance.
- 🟡 MED line 232-270: risk-matrix grid has no `<th>`/`aria-label` so screen readers can't read it. The axis labels "High/Med/Low" are decorative spans.
- 🟡 MED line 412-432: connector fleet rows use a 4-column grid (`20px 1fr auto auto`) but the latency column right-aligns inline-style — small but inconsistent with the table-cell pattern used elsewhere.
- 🔵 LOW line 38-65: a 33-row demo dataset is rendered at module scope. Tree-shakers can't eliminate it because exports are referenced. Wrap with `process.env.NODE_ENV === "development" ? ... : []` or, ideally, behind a feature flag.
- 🔵 LOW line 285: `<table className="w-full border-collapse">` — no `<caption>` or `aria-label`.

### frontend/src/app/projects/page.tsx
**Purpose:** Project list with filtering + search.
**Reviewed lines:** 351.

#### Issues
- 🟠 HIGH line 66-78: raw `fetch` inside `useEffect` instead of using the React-Query hook `useProjects()` that already exists in `lib/queries/projects.ts`. Inconsistent caching means hard refresh shows stale data here but fresh data on `dashboard`. Migrate.
- 🟡 MED line 89-101: client-side filter on the in-memory list. For an org with 10k+ projects this is fine for *display* (rendering is the bottleneck) but the search index ignores `description`, `source_system`, `target_system`. Pre-filter on the server.
- 🟡 MED line 125: `grid-cols-6` is unconditional — same mobile breakage as dashboard.
- 🟡 MED line 138-144: `<input>` has no debounce; search hits state every keystroke. Combined with re-render-the-table-of-thousands, can hitch typing.
- 🟡 MED line 233-287: rows are `cursor-pointer` but only the project-name cell, the ArrowUpRight cell, and the avatar cell are clickable. Same misleading hover affordance as dashboard.
- 🔵 LOW line 337-350: `formatRelative` returns `${s}s` without an "ago" suffix for sub-minute values. Inconsistent with the rest.
- 🔵 LOW line 191-216: header cells use inline `{ l: "", w: 4 }` config but `width` is a CSS pixel that won't shrink on overflow — the table forces a `min-w-[1280px]` horizontal scroll on any viewport <1280px. Acceptable but worth a callout.

### frontend/src/app/projects/new/page.tsx
**Purpose:** Project create form.
**Reviewed lines:** 244.

#### Issues
- 🟠 HIGH line 55-74: raw fetch sending `source_system`, `target_system`, `environment` — none of which exist on `ProjectCreate` in `lib/api-types.ts` (line 67-72, fields are `name/description/risk_level/migration_type`). The backend will silently drop these or 422. Verify with the actual backend schema or update types.
- 🟡 MED line 50-80: no `useCreateProject()` React-Query mutation reuse; same dual-pattern problem.
- 🟡 MED line 64-66: `source_system: sourceSystem || undefined,` — fine, but combined with the `select` having a placeholder, the user can submit with no source. No validation banner.
- 🔵 LOW line 109-117: `Field` component takes `label` and `required` — but the `*` is on the **label** not the input. Screen readers don't connect them via `aria-required` either.
- 🔵 LOW line 169-196: env radios use a hidden input + label. Keyboard support: tab focuses the *label* but space/arrow keys don't change selection. Use `role="radiogroup"` on the wrapper and `aria-checked` on each.

### frontend/src/app/projects/[id]/page.tsx
**Purpose:** Project detail (overview tab).
**Reviewed lines:** 633.

#### Issues
- 🟠 HIGH line 147-155: `fetch(...).then((data) => setProject(data ?? null)).catch(() => setProject(null))` — the catch swallows the error silently. The page renders "—" everywhere and the user has no signal that the call failed vs. that the project really has no data.
- 🟠 HIGH line 114-124: `DEFAULT_PHASES` array — a UI-side fallback for phases. If the backend returns 9 phases in a different order, you'd still see 9 default phases when the API returns `null`. Make the empty state explicit: "No workflow yet · start it →".
- 🟡 MED line 215: `<ErrorBanner message={error}>` is rendered, but `error` is never set anywhere on the page (the only `setError` is in the unused `const [error, setError] = useState("")` declaration on line 145, never written to). Dead state.
- 🟡 MED line 199-211: actions `<Pause>`, `Sprints`, `Open workspace`, `Ask Helix` are dead buttons — no handlers wired. Inconsistent with the `Link` wrappers on a couple of them.
- 🔵 LOW line 246-296: phase ticker `gridTemplateColumns: repeat(${phases.length}, 1fr)` won't scroll when phases > ~12. Mobile breaks.

### frontend/src/app/projects/[id]/agents/page.tsx
**Purpose:** Per-project agents workflow.
**Reviewed lines:** 100.

#### Issues
- 🔴 CRITICAL: this entire page renders **mock-data flow nodes** (`const FLOW = [...]` lines 8-18), with no project-id fetching whatsoever. It's a placeholder identical for every project. The project name says "Untitled project" line 25. Should be wired or hidden.
- 🟡 MED line 25: hard-coded `projectName="Untitled project"` and `projectStatus="draft"` — every per-project page shows this. The `ProjectShell` should fetch the project itself, not require these props.
- 🟡 MED line 36-41: each `FlowNode` is rendered with hand-keyed colors via a `color` prop literal — these are typed as a string union but coupled to a `palette` Record. Status is a free string; e.g. `"queued"` doesn't appear in the palette but goes through `StatusBadge`. The two color systems collide.
- 🔵 LOW: buttons "Approve / Request changes / Reject" are dead.

### frontend/src/app/projects/[id]/developer-workspace/page.tsx
**Purpose:** Per-project workspace (mock).
**Reviewed lines:** 64.

#### Issues
- 🔴 CRITICAL: zero API. The artifact tabs, versions, and code-pane diff are static strings. This routes off `ProjectShell` with `projectName="Untitled project"`.
- 🟡 MED: duplicates **most of** `/developer-workspace/page.tsx` and `/developer-workspace/[id]/page.tsx`. Three "developer workspace" pages exist with three different layouts. Consolidate.

### frontend/src/app/developer-workspace/page.tsx
**Purpose:** Three-pane IDE for artifact review (mock data only).
**Reviewed lines:** 869.

#### Issues
- 🔴 CRITICAL: 100% mock data — `ARTIFACT_TREE`, `VERSION_HISTORY`, `DIFF_LINES`, `AI_REVIEWS` are static literals. There is **no `id` param**, no project context. The page is reachable from sidebar but doesn't represent any real artifact. Either gate behind a feature flag or replace with a "select an artifact" empty-state.
- 🟠 HIGH line 175-194: `ProjectSwitcher` is a button with no handler — clicking does nothing. Same with the search input on line 786-792 (uncontrolled, no submit).
- 🟠 HIGH line 309-510: `DiffPane` is 200+ lines of inline-style positioning. No alternate "side-by-side" view; pure unified diff. Hard to maintain.
- 🟡 MED line 21-30: `ArtifactFile.suggestions?: number` but `ai?: "ok" | "warn"`. The tree color computation collapses both — no encoded relationship between count and severity. `suggestions: 3` for a `"warn"` file makes sense; for an `"ok"` file it's confusing.
- 🟡 MED line 686-700: `AskHelix` input has no submit handler; pressing `Enter` does nothing. The `<Kbd>↵</Kbd>` advertises functionality that doesn't exist.
- 🟡 MED line 753-759: `style={{ height: "calc(100vh - 44px - 81px)" }}` — magic numbers (topbar 44px + page header 81px). One layout change in `AppShell` and this becomes wrong. Use CSS grid + `1fr` or `flex-1`.
- 🔵 LOW: the entire file is `"use client"`. With ~870 lines and `lucide-react` imports, this contributes meaningfully to first-paint bundle. Code-split via dynamic import on the IDE shell.

### frontend/src/app/developer-workspace/[id]/page.tsx
**Purpose:** Real-API artifact review (AI code review).
**Reviewed lines:** 213.

#### Issues
- 🟠 HIGH line 48-53: `fetch(...).then((r) => (r.ok ? r.json() : null)).then(setArtifact)` — on 404 sets `null` without telling the user. No error UI for the "this artifact doesn't exist" case.
- 🟡 MED line 70-73: errors are stringified via `setError(err instanceof Error ? err.message : "Review failed")`. `ErrorBanner` shows a single line; AI review failure modes (rate limit, model down, prompt-too-large) deserve richer messages.
- 🟡 MED line 117: `artifact.content_hash?.slice(0, 16)` — `content_hash` is non-null in the type. The `?.` is dead. Cosmetic.
- 🟡 MED line 92-96: the file explorer in the left rail is **hard-coded** ("plan_v1.md", "ddl.sql", …) regardless of which artifact is open. Wire to `/artifacts?project_id=`.
- 🟡 MED line 195-208: reviewers ("Avery Johnson", "Sofia Marin", "Rohan Patel") are hard-coded — these should be fetched from the project's assignees.
- 🔵 LOW line 76-77: `severityChip` returns `"red" | "amber" | "indigo"` — three of the *legacy* chip tone names. The new tones are `err / warn / brand`. Both still work due to the alias map in `Chip.tsx`, but consistency would help.

### frontend/src/app/agents/page.tsx
**Purpose:** Global agents (BMAD pipeline) page.
**Reviewed lines:** 819.

#### Issues
- 🔴 CRITICAL: every byte of data is mock (`BMAD_PIPELINE`, `WORKFLOW_RUNS`, `TOKEN_USAGE`). The "Live" chip on line 199 is theater. Replace or hide.
- 🟠 HIGH line 136-139: `const firstRun = WORKFLOW_RUNS[0]!;` — non-null assertion on a possibly-empty array (it isn't today but defensive coding matters in TS strict). Use `?? defaultRun` and a real loading skeleton.
- 🟠 HIGH line 369-371: `boxShadow: isRunning ? "0 0 0 3px rgba(79,70,229,0.08)" : "var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04))"` — the indigo color is hard-coded rather than `var(--con-brand)`. Theme tweak does not reach this glow.
- 🟡 MED line 391-447: `PipelineNode` mixes Tailwind classes and inline style with about a 50/50 split. The hybrid is hard to scan and prevents purgeCSS from being effective.
- 🟡 MED line 519-611: `PhasesView` swim-lanes use a 7-column grid with `minmax(150px, 1fr)` — under 1050px the columns collide. No mobile fallback (no `overflow-x-auto` wrapper around the column container, despite line 522 wrapping the `Card`).
- 🟡 MED line 761-819: `GateNode` is decorative — the rejected-branch arrow is part of a separate `mt-6` block; this is visual debt that doesn't render the actual rejection state from data.
- 🔵 LOW line 217-242: phase ticker progress bars (line 311-323) hard-code 55% width for the running stage. Should derive from data once available.

### frontend/src/app/validation/page.tsx
**Purpose:** Validation Center.
**Reviewed lines:** 345.

#### Issues
- 🔴 CRITICAL: 100% mock — `VALIDATION_CHECKS`, `TYPE_BREAKDOWN`, `RECON_TREND` are inline literals. No API call. Same banner-or-hide recommendation.
- 🟠 HIGH line 240-243: search `<input>` is uncontrolled — typing has no effect on filtered rows. Wire to a state.
- 🟡 MED line 156-170: the "92.4%" pass rate hero and the donut summary work off different *implicit* totals (the hero implies 70% pass-rate-shape from `summary.pct` literals line 126-129, not from `passed/total`). Two sources of truth.
- 🟡 MED line 215-230: "3 validation rules are failing" alert is also static. The number is fictional.

### frontend/src/app/reconciliation/page.tsx
**Purpose:** Reconciliation Center.
**Reviewed lines:** 120.

#### Issues
- 🟡 MED line 30-31: `const reconRuns: ReconRun[] = [];` — the page renders an explicit empty state, but the metric cards (lines 54-58) display "0%" / "0" which is misleading when the data is actually absent.
- 🟡 MED line 33-43: action buttons "Export Report" and "Run Reconciliation" are dead.
- 🔵 LOW line 13: imports `formatDate/formatTime/formatNumber` from utils but uses them only inside the empty list. Bundler dead-code-eliminates this fine, but worth noting.

### frontend/src/app/approval/page.tsx
**Purpose:** Design exploration for approval-UX variants.
**Reviewed lines:** 710.

#### Issues
- 🟠 HIGH: this entire page is a **design-system showcase**, not a functional approval workflow. It lives at `/approval` in the production route table. End users will see "Three patterns for the human-approval node…" with mock-blurred backgrounds. Either remove from production routes or namespace under `/design/approval`.
- 🟡 MED line 28-147: `MockPage` is 100 lines of inline `style={{}}` decorative scaffolding. Move to a `/design` subroute.
- 🔵 LOW line 446-572: `VariantCard` is reusable infrastructure that doesn't belong in a page file.

### frontend/src/app/files/page.tsx, plugins/page.tsx, reports/page.tsx, templates/page.tsx
**Purpose:** Stubs for unbuilt features.
**Reviewed lines:** 39, 39, 38, 39.

#### Issues
- 🔵 LOW: all four are near-identical EmptyState pages. Factor into a single `<ComingSoonPage feature="…" />` component reused by each route. Saves 100+ lines of repeated JSX.

### frontend/src/app/connectors/page.tsx
**Purpose:** Connector catalog + 3-step connect modal.
**Reviewed lines:** 1223.

#### Issues
- 🟠 HIGH line 415-423: `setTimeout(() => { setTestState(Math.random() > 0.15 ? "ok" : "fail"); }, 1400);` — the "Test connection" feature is a **simulator** with a fixed 85% success rate and a fake 1.4s delay. Production users running this against real DBs will see fictional pass/fail outcomes. Replace with a real call to `/api/v1/connectors/test`.
- 🟠 HIGH line 134-224: `FIELDS_FOR(key)` hardcodes per-provider form schemas. These should be driven by `GET /api/v1/connectors/registry` schema descriptors so adding a new connector doesn't require a frontend release.
- 🟡 MED line 219-223: the `default:` branch of `FIELDS_FOR` returns a tiny 3-field form for "anything else", including legitimate connectors that just haven't been added to the switch. Should crash loudly during dev.
- 🟡 MED line 489-1000: `ConnectModal` is 510 lines. Split into `ProviderStep` / `CredentialsStep` / `TestStep` and a parent `ConnectorWizard`.
- 🟡 MED line 405-487: focus is *not* trapped inside the modal. Tab key drops out of the modal into the underlying page. Add a focus-trap or use a headless-UI dialog primitive.
- 🟡 MED line 528-532: modal close button has `cursor: "pointer"` (style attr) but inherits no aria-label on the wrapper. Verify the `<button type="button">` line 527 itself has accessible text (here, the `<X size={16}>` is the only content — needs `aria-label="Close"`).
- 🔵 LOW line 248: `letter` and `color` properties on `ConnectorRow` are unused (`AppIcon` derives its own). Dead props.
- 🔵 LOW line 35: `instances: number | string` — union type is unnecessary if it's always `"—"` until wired. Make `null` and render `null` → "—".

### frontend/src/app/settings/page.tsx
**Purpose:** Profile + appearance + notifications + sign-out.
**Reviewed lines:** 454.

#### Issues
- 🟠 HIGH line 296-298: notification toggles store to **local React state only** — `setEmailDigest`/`setWorkflowAlerts`/`setValidationFail` are `useState` with no persistence. Comments say "Stored locally" but flipping a toggle then navigating loses the state. Add `localStorage` persistence, or persist to `useTweaks`/preferences API.
- 🟡 MED line 115-136: `save()` on profile name calls `/users/me` PATCH but doesn't refresh AuthContext — the sidebar avatar continues to show the old name until next reload. Add a `refreshUser()` action to AuthContext or rerun `/auth/me`.
- 🟡 MED line 432-450: custom `Toggle` reimplemented here when an identical one (modulo styling) is in `TweaksPanel`. Move to shared `ui/Toggle.tsx`.
- 🔵 LOW line 78-92: section-nav `<a href="#profile">` jumps work but offer no active-state styling — hard to tell which section you're in.

### frontend/src/app/admin/page.tsx
**Purpose:** Admin landing.
**Reviewed lines:** 70.

#### Issues
- 🟡 MED line 37-40: MetricCard values (`24`, `7`, `OK`, `1.2K`) are static strings. Replace with `useQuery({ queryKey: ["admin-stats"] })`.
- 🔵 LOW line 27-32: tiles link to `/admin/roles`, `/admin/connectors`, `/admin/custom-connectors`, `/admin/notifications`, `/admin/import-export` — but **none of these routes exist** in the current `app/admin/*` tree. Clicking any of them 404s. Either implement, hide, or render with a "Coming soon" badge.

### frontend/src/app/admin/users/page.tsx
**Purpose:** User list.
**Reviewed lines:** 96.

#### Issues
- 🟠 HIGH line 44: `const data = users.length > 0 ? users : DEMO;` — when the API returns an empty array, the page silently displays 5 fake demo users (lines 21-27). This means: in a fresh deployment the admin will see fictional "Avery Johnson / Mei Chen" etc. as if they're real users. Critical security/operational risk. Use the genuine empty state instead.
- 🟡 MED line 37-42: `fetch(...).catch(() => setError("Failed to load users"))` — but `error` is wired to `<ErrorBanner>` so users see "Failed to load users" while *also* seeing the demo data. Inconsistent.
- 🟡 MED line 84: `Manage` button is a `<button>` with no handler.

### frontend/src/app/admin/audit-logs/page.tsx
**Purpose:** Audit logs.
**Reviewed lines:** 112.

#### Issues
- 🟠 HIGH line 42: same `data = logs.length > 0 ? logs : DEMO` pattern — production deployments show fictional audit entries from 2026-05-23. Same security/operational concern as users page.
- 🟡 MED line 53-69: search input is uncontrolled; filter pills are static; "Export CSV" button has no handler.

### frontend/src/app/admin/system-health/page.tsx
**Purpose:** System health dashboard.
**Reviewed lines:** 84.

#### Issues
- 🟡 MED line 28: assumes `data.components` is an array of `ComponentStatus[]`. The actual backend `HealthResponse` (lib/api-types.ts line 357-361) returns `components: Record<string, HealthComponent>` — a **map**, not an array. This page will crash or display nothing as-is.
- 🟡 MED line 24-30: no refresh on interval; the page is static after first load. Either poll or expose a refresh button (which exists but does nothing).
- 🔵 LOW line 64: `.replace(/_/g, " ")` per row — fine; could be a util.

### frontend/src/app/admin/agent-mapping/page.tsx
**Purpose:** Map each BMAD agent → (provider, model).
**Reviewed lines:** 289.

#### Issues
- 🟡 MED line 116-119: "simple mode" propagates the analyst mapping to every agent. If analyst row is empty the save no-ops silently; if analyst is set, all 6 agents get the same temperature and max_tokens. Make the UX explain this clearly (line 158-176 partially does).
- 🟡 MED line 60-67: `useCallback` wrapped fetcher captures `authHeader` from closure — but `authHeader` is recreated on each render (it's a `const` inside the component body, line 58). The `useCallback` cache key omits `authHeader`, suppressing the lint rule via `eslint-disable-next-line`. The result still functionally works because `loadProviders` re-runs from `loadProviders` recreation via the `[token]` dep, but it's an antipattern.
- 🟡 MED line 215, 219, 234, 252: heavy use of `disabled={disabled}` based on `mode === "simple"`. Disabled `<select>` is the WCAG worst-case for keyboard nav — combine with the `disabled:opacity-50` class to lose contrast on top of that.
- 🔵 LOW line 246-253: smart-dropdown vs free-text input switch is good UX, but breaks if the user typed a custom model id in advanced mode then switches to simple mode — input becomes a select that doesn't contain the previous value.

### frontend/src/app/admin/llm-settings/page.tsx
**Purpose:** LLM provider configuration.
**Reviewed lines:** 527.

#### Issues
- 🟠 HIGH line 124-138: `startEdit` blanks the `api_key` field. The placeholder says "Leave blank to keep current key" but a paranoid admin can paste a key and accidentally rotate. Add a "Show current key" reveal flow (or remove the field entirely from edit mode in favor of a separate "Rotate key" action).
- 🟡 MED line 156-181: `updateProvider` calls PATCH then `rotate-key` POST sequentially — non-atomic. Provider name PATCH could succeed while key rotation 401s mid-flight, leaving the form thinking the save failed.
- 🟡 MED line 89-96: catalogue fetch ignores errors silently. If the endpoint 500s, the form falls back to `<input>` for all model fields — confusing UX with no banner.
- 🟡 MED line 213-215: `apiKeyRequired = !KEYLESS_PROVIDERS.has(form.provider_type)`. The Set here (line 44) is `{"bedrock", "vertex"}` — but the setup wizard's KEYLESS_PROVIDERS (line 89) is `{"bedrock", "vertex", "local"}`. The two pages disagree about "local"; this is a real-world bug if the user adds a local Ollama provider via the wizard and tries to edit it here.
- 🔵 LOW line 240-251: testResult banner is `bg-[var(--con-ok-soft)]`/`bg-[var(--con-err-soft)]` but `border-hx` for both — fails to convey severity via border color.

### frontend/src/app/projects/[id]/sprints/page.tsx
**Purpose:** Sprint dashboard.
**Reviewed lines:** 468.

#### Issues
- 🟠 HIGH line 119-127: `handleSeed` calls `seedSprints` then `window.location.reload()`. Two issues: (1) hard reload defeats React Query cache and loses any unsaved UI state, (2) on a slow API the reload lands on an inconsistent intermediate state. Replace with `queryClient.invalidateQueries(["sprints"])`.
- 🟠 HIGH line 109-117: `useMemo` for `completionPct` divides `storyPointsDone / storyPointsTotal` without guarding for `total === 0`. Although `metrics.storyPointsTotal` defaults to 0 from the adapter (api.ts line 175), the page handles this with a fallback `|| 0` but `Math.round(NaN)` would be `NaN`.
- 🟡 MED line 80-91: parallel `Promise.all` of three fetches — but the second `useEffect` (line 94-107) depends on `active` which comes from the first. So this *can't* race, but it does fire two waves of requests when a single combined endpoint would do.
- 🟡 MED line 369-386: `NewSprintModal` is a focused, simple form — but the date inputs accept any range with no UX warning when `endDate < startDate`. Form validation would help.
- 🟡 MED line 373-376: backdrop close-via-click works (`e.target === e.currentTarget`), but pressing Escape outside the modal still bubbles to whatever else. Use a focus trap.
- 🔵 LOW line 222-253: the metric cells display percentages that may be `NaN%` if `metrics.storyPointsTotal === 0` and the adapter fallback hasn't kicked in.

### frontend/src/app/projects/[id]/sprints/board/page.tsx
**Purpose:** Sprint planning kanban board.
**Reviewed lines:** 639.

#### Issues
- 🟠 HIGH line 76-95: `handleMove` is optimistic — the rollback uses `snapshot` captured *during* the setter call. If the user drags two tasks fast, the second drag's snapshot may include the first drag's optimistic update; rolling back the second drag could restore the optimistic state of the first. Capture from `tasks` outside the setter or maintain a per-task pending list.
- 🟠 HIGH line 109-110: `setSelectedSprintId(act?.id ?? list[0]?.id ?? "")` — if the user has only completed sprints and no active one, the board lands on the first completed sprint. That's probably the right default but should be communicated ("No active sprint — showing latest completed").
- 🟡 MED line 277-432: `TaskDetailPanel` is a 150-line component that renders unconditionally inline. Lazy-load or move to a separate file.
- 🟡 MED line 451: `AI_AGENTS = ["", "Mary", "John", ...]` — agent names are display strings, not BMAD codes (`bmad-agent-analyst`, etc.). The form submits `ai_agent: aiAgent` (line 498) so the backend gets "Mary" instead of "bmad-agent-analyst". Inconsistent with `agent-mapping/page.tsx` which uses codes.
- 🟡 MED line 89-92: `setTimeout(() => setMoveError(null), 4000)` — no cleanup. If component unmounts within 4s the setState fires on unmounted component (React 18 warns).
- 🔵 LOW: `Tabs` with `variant="pill"` is used as the sprint selector. With 10+ sprints this overflows; the surrounding `overflow-x-auto` (line 199) helps, but ideally use a `<select>` for >5 sprints.

### frontend/src/app/projects/[id]/sprints/execution/page.tsx
**Purpose:** Live execution monitor with SSE.
**Reviewed lines:** 389.

#### Issues
- 🔴 CRITICAL line 91-101: `subscribeToExecutions` passes the **JWT in the URL query string** (`?token=...`, see `lib/sprints/api.ts` line 441). This is a known anti-pattern: tokens leak into proxy logs, browser history, the `Referer` header. The code comment acknowledges it. Move to a same-origin cookie + `EventSource` with `withCredentials: true`, or fetch + ReadableStream.
- 🟠 HIGH line 73-83: `fetchActiveSprint` runs **after** the SSE stream subscribes. The stream is keyed only on `projectId` so it pulls *all* executions for the project, not just the active sprint's. Filtering to the active sprint must happen client-side (which it doesn't — `executions` is global).
- 🟡 MED line 122-129: `useMemo` over `counts` with no caching of the prior `executions` value — every snapshot from SSE re-derives it. Fine for 50 rows; concern with >1000.
- 🟡 MED line 196-205: `streamLive = false` after the SSE errors out, but the page doesn't expose a "Reconnect" button. Add manual reconnect or auto-retry with backoff.
- 🟡 MED line 312-356: `AgentExecutionCard` does not show the log diff between snapshots; large logs will rerender the whole row every 2 seconds.
- 🔵 LOW line 46-51: `formatDuration(ms / 1000)` does integer rounding — `1500ms` → `2s`. Use `Math.floor` for the seconds field, or display as `1.5s`.

### frontend/src/app/projects/[id]/sprints/mapping/page.tsx
**Purpose:** React-Flow migration graph.
**Reviewed lines:** 277.

#### Issues
- 🟡 MED line 70-79: `agentBreakdown` derived via `Map` + `Array.from` — fine for ~20 nodes, but the `sort((a,b) => b.count - a.count)` could stabilize on equal counts.
- 🟡 MED line 94-102: seeding pattern repeated again — fourth copy of `handleSeed`. Extract.
- 🔵 LOW line 175: `style={{ maxWidth: 320 }}` on the aside — inline pixel cap fights the responsive grid. Use Tailwind `max-w-[320px]`.

### frontend/src/app/projects/[id]/sprints/timeline/page.tsx
**Purpose:** SVG gantt timeline.
**Reviewed lines:** 419.

#### Issues
- 🟠 HIGH line 73-80: `range.min` computed from `Math.min(...starts)` will crash on >100k sprints (call-stack overflow). For this app, irrelevant — but write `starts.reduce((m, x) => Math.min(m, x), Infinity)`.
- 🟠 HIGH line 36-37: `CHART_WIDTH = 1100` is a fixed pixel SVG width. On mobile (<1100px) it overflows. The wrapping `overflow-x-auto` (line 219) saves it, but the SVG is not viewBox'd — touch zoom doesn't help.
- 🟡 MED line 90-106: month markers loop in UTC. If the project spans a DST boundary, labels appear an hour off (cosmetic since it's monthly, but the `setUTCDate(1)` reset can land on the wrong month for users in negative UTC offsets).
- 🟡 MED line 110-139: `checkpoints` derives migration milestones from sprint indexes (`s(0)` through `s(5)`) — if a project has fewer than 6 sprints, the function falls back to the last sprint repeatedly, stacking checkpoint dots in the same location. The visual breaks.
- 🔵 LOW line 219-401: massive inline SVG. Hard to unit-test. Factor into a `<TimelineSvg sprints={…} />` component.

### frontend/src/app/projects/[id]/sprints/analytics/page.tsx
**Purpose:** Cross-sprint analytics.
**Reviewed lines:** 307.

#### Issues
- 🟡 MED line 36-44: `AGENT_BREAKDOWN` is hard-coded mock data; the title says "Agent contribution" but the values are fictional. Add a banner or hide.
- 🟡 MED line 174-177: "AI vs Human / 71% / 29%" is a string literal — not derived. Same problem.
- 🟡 MED line 89-105: `validationTrend` and `reconTrend` derive from sprint metrics — but `Sprint.metrics.validationCoveragePct` is the cumulative pct, not per-sprint delta. The chart title "trend" is misleading.

### frontend/src/app/projects/[id]/sprints/dependencies/page.tsx
**Purpose:** Task dependency graph.
**Reviewed lines:** 337.

#### Issues
- 🟡 MED line 137-186: layout assigns column by status — but if a task has no incoming edges, it can collide with another in the same column (`PAD_Y + i * ROW_H`). Tasks visually overlap if two backlog tasks exist.
- 🟡 MED line 268-272: ReactFlow renders without virtualization. For sprints with hundreds of tasks this would lag.
- 🔵 LOW line 73: `data.title.length > 30` truncate — better to use CSS `text-overflow: ellipsis` so it adapts to the actual rendered width.

### frontend/src/app/projects/[id]/sprints/approval/page.tsx
**Purpose:** Sprint approval center.
**Reviewed lines:** 255.

#### Issues
- 🟡 MED line 96-103: `handleApprove` and `handleReject` fire the API call but **discard the result**. If the backend rejects ("you don't have permission"), the optimistic decision stays in `decisions` state forever. Wire to a try/catch and revert on failure.
- 🟡 MED line 84-86: `useMemo` over `[approvals, decisions]` but the dep array is wrapped with `eslint-disable-next-line` — the lint rule was masking the fact that `resolve` is recreated every render and is *not* listed. Resolve closes over `decisions` so deps are correct, but the eslint-disable is over-broad.
- 🔵 LOW line 244-253: `KindRow` is a private helper — fine, but could be moved to `components/sprints/primitives.tsx` for reuse.

### frontend/src/app/projects/[id]/sprints/risks/page.tsx
**Purpose:** Sprint risk dashboard.
**Reviewed lines:** 313.

#### Issues
- 🟡 MED line 45-50: `LEVEL_CELL` maps risk level → fixed heatmap cell coordinates. This means every "critical" risk lands in cell `(4,4)` and every "low" in `(1,0)`. The heatmap is essentially a 4-bucket count — not a real likelihood × impact analysis. Either fetch real coordinates or rename "Heatmap" to "Severity bucket distribution".
- 🟡 MED line 105-112: the same `grid[r.level]` is incremented; subsequent risks of the same level pile on top of each other. Same conceptual issue.
- 🟡 MED line 177-178: "AI confidence 78%" and "Mitigation 62%" are hard-coded literals. Mark as TODO or remove.

### frontend/src/app/projects/[id]/sprints/releases/page.tsx
**Purpose:** Release dashboard.
**Reviewed lines:** 336.

#### Issues
- 🟡 MED line 76-82: `checklistDone` divides by `checklist.length`; safe when zero (early-returns 0).
- 🟡 MED line 173-198: stage timeline is a horizontal flex row — `flex-shrink-0` plus parent `overflow-x-auto` works but the **active stage isn't auto-scrolled into view**. With 7 stages and an active stage at index 5, mobile users have to scroll right to see what's current.
- 🟡 MED line 165-167: `upcoming.targetEnvironment.toUpperCase()` — direct string `.toUpperCase()` on a free-form field with no validation. If backend returns "Prod" capitalized differently the badge wouldn't match the chip-tone switch on line 254. Normalize at the adapter layer.

### frontend/src/components/layout/AppShell.tsx
**Purpose:** Sidebar + Topbar + content shell.
**Reviewed lines:** 65.

#### Issues
- 🟡 MED line 36-38: `trailLabels` derives string crumbs from object crumbs — but the `<PageHero>` itself accepts the original `crumbs` array (line 55) AND `<Topbar crumbs={trailLabels}>` gets the strings (line 45). So breadcrumbs render **twice**: once in the page hero, once in the topbar — same labels. Confusing. Pick one.
- 🟡 MED line 41: `grid-cols-[232px_1fr]` is unconditional. On mobile (<lg), the `<Sidebar>` (which has `hidden lg:flex` line 161) becomes invisible but the 232px column still exists, pushing content 232px right with no sidebar to fill it. Use `lg:grid-cols-[232px_1fr]` or wrap Sidebar in a positioned container.

### frontend/src/components/layout/AdminShell.tsx
**Purpose:** Admin sub-nav + content.
**Reviewed lines:** 73.

#### Issues
- 🟡 MED line 51: `pathname.startsWith(item.href)` will mark `/admin/users` active when on `/admin/users-foo` — false positive. Use exact match for the `/admin` root case (already done) plus a `===` || `+"/"` fix for the others.
- 🔵 LOW line 28-29: the ADMIN_NAV array references `/admin/custom-connectors`, `/admin/connectors`, `/admin/roles`, `/admin/notifications`, `/admin/import-export` — none of these routes exist. Same dead-link concern as `/admin/page.tsx`.

### frontend/src/components/layout/ProjectShell.tsx
**Purpose:** Per-project header + tabs + content.
**Reviewed lines:** 72.

#### Issues
- 🟡 MED line 18-29: hard-coded tab list. Missing `/sprints/*` tab (the project's sprints surface). Inconsistent with `[id]/page.tsx` which links to `/sprints` only via the actions menu (line 199-203). Tab the sprints sub-tree.
- 🟡 MED line 50: `pathname.startsWith(href)` — same active-state false positives as AdminShell.
- 🔵 LOW: the shell hard-codes `projectName: "Untitled project"` requirement, so per-project pages have to know the name in advance. Move to a `useProject()` query inside the shell.

### frontend/src/components/layout/Sidebar.tsx
**Purpose:** Persistent left nav.
**Reviewed lines:** 194.

#### Issues
- 🟠 HIGH line 106-125: `WorkspaceSwitcher` is a button that does nothing — clicking the chevron does not open a menu. Misleading affordance.
- 🟠 HIGH line 127-138: `SearchTrigger` says "⌘K" but pressing ⌘K does nothing — no global command-palette is wired up. Remove the shortcut hint or implement.
- 🟠 HIGH line 140-151: `UserFooter` defaults to `"Avery Johnson"` / `"Platform Admin"` regardless of who's logged in. **The real user from `useAuth().user` is never rendered.** Critical for any multi-user deployment.
- 🟡 MED line 161-191: the sidebar is `<aside className="hidden lg:flex …">` — mobile users get nothing, no hamburger menu. There's no `<MobileNav>` component anywhere in the codebase.
- 🟡 MED line 156-158: `isActive("/dashboard")` matches `pathname === "/dashboard" || pathname === "/"` — meaning the dashboard nav is active on the marketing landing page. The landing page has its own `WebsiteNav` so this only matters when both render (it shouldn't), but it's a leaky condition.
- 🟡 MED line 78-81: `<Link>` with `count` prop — but no `NavItem` in `PRIMARY` / `RESOURCES` / `ADMIN` arrays sets `count`, so the rendered counts are always blank. Dead feature.

### frontend/src/components/layout/Topbar.tsx
**Purpose:** Sticky 44-px top header.
**Reviewed lines:** 60.

#### Issues
- 🟡 MED line 41-56: "Notifications" and "Ask Helix" buttons have no handlers. Dead UI.
- 🟡 MED line 19-20: `crumbs = []` default + prefix "Helix" — when used without crumbs, the trail shows only "Helix" which is meaningless. Hide the breadcrumb nav when empty.

### frontend/src/components/layout/HelixLogo.tsx
**Purpose:** Brand logo.
**Reviewed lines:** 49.

#### Issues
- 🔵 LOW line 47: `HeroHelixArt` is exported but returns `null` — kept "for backward compat". Remove and update the one importing call site (`app/page.tsx` line 20).

### frontend/src/components/layout/PageHero.tsx
**Purpose:** Editorial page header.
**Reviewed lines:** 72.

#### Issues
- 🟡 MED line 33: outer padding `px-10 pt-8 pb-6` is hard-coded — but content area uses `px-10 py-6` (AppShell line 57). Tight coupling between two components on a literal value.
- 🔵 LOW line 19: `withArt` prop is documented as ignored — remove.

### frontend/src/components/ui/Button.tsx
**Purpose:** Calm button primitive.
**Reviewed lines:** 73.

#### Issues
- 🔵 LOW line 4: `Variant` includes `"primary"` and `"dark"` with identical class strings (lines 20-21 and 32-33). Decide which is canonical.
- 🔵 LOW line 56: `cn(... "whitespace-nowrap")` — combined with `disabled:opacity-50` produces a focus ring on disabled buttons that draws attention to an inactive control.

### frontend/src/components/ui/Card.tsx
**Purpose:** Calm card container.
**Reviewed lines:** 110.

#### Issues
- 🔵 LOW line 38: padding values (`p-3.5`, `p-[18px]`, `p-6`) are mixed Tailwind utility + arbitrary class. The arbitrary `p-[18px]` doesn't compose with `bodyClassName="p-0"` because both produce padding-* on the same element; `bodyClassName` wins. Verify intent.

### frontend/src/components/ui/Chip.tsx, StatusBadge.tsx, ProgressBar.tsx, Kbd.tsx
**Reviewed lines:** 66 + 57 + 44 + 19.

#### Issues
- 🔵 LOW: `Chip` legacy aliases (`indigo`, `green`, `amber`, `red`) — keep but mark deprecated in a comment.
- 🔵 LOW (StatusBadge.tsx line 28): `pending` maps to `"warn"` tone; on the dashboard a "Pending" status renders as orange, but on the connectors page it might be expected to be "neutral". Inconsistent semantics across the app — clarify a single status taxonomy.

### frontend/src/components/ui/Avatar.tsx
**Purpose:** Initials avatar.
**Reviewed lines:** 62.

#### Issues
- 🔵 LOW line 4: `palette` has 8 entries; `name.charCodeAt(0) % palette.length` produces only 8 unique colors. Two users with names starting at the same `charCodeAt(0) % 8` collide. Use `hashCode(name) % palette.length`.

### frontend/src/components/ui/AreaChart.tsx, Donut.tsx, Sparkline.tsx
**Reviewed lines:** 119 + 69 + 36.

#### Issues
- 🟡 MED (AreaChart.tsx line 44): `Math.max(...rows.flatMap((d) => [d.a || 0, d.b || 0]))` — `flatMap + max + spread` performs 3 array allocations. For 30 data points fine; for hourly metrics across 365 days, slow.
- 🟡 MED (AreaChart.tsx line 31-32): `width = 720, height = 220` defaults but the component uses `width="100%"`. The viewBox uses the fixed width — on a narrow container the labels truncate strangely. Test with a 320px wide parent.
- 🔵 LOW (Donut.tsx line 32-34): `total = ... || 1` defends against division by zero, but with `total=1` and `value=0`, every segment renders as empty arc — but the strokeDasharray `${dash} ${c - dash}` produces `0 c`, which is fine. Just noting the silent default.

### frontend/src/components/ui/EmptyState.tsx, LoadingState.tsx, ErrorBanner.tsx, MetricCard.tsx
**Reviewed lines:** 25 + 19 + 32 + 128.

#### Issues
- 🔵 LOW (MetricCard.tsx line 33): default `sparkColor` is `var(--con-brand)`; combined with `accent` for the value, you can end up with two distinct accent shades on the same card. Document hierarchy.

### frontend/src/components/ui/Table.tsx
**Purpose:** Semantic table primitives.
**Reviewed lines:** 94.

#### Issues
- 🔵 LOW line 11: `Table` exposes a `minWidth` prop — but no callers in the codebase use it (verified: every page that needs a minWidth uses an inline `<table className="min-w-[1280px]">` instead, e.g. projects/page.tsx line 189). Either adopt across the app or remove the prop.

### frontend/src/components/ui/Tabs.tsx
**Purpose:** Pill + underline tabs.
**Reviewed lines:** 79.

#### Issues
- 🔵 LOW line 8-10: `Tab.count` is optional — but a count of 0 still renders the badge. Wrap with `count > 0 &&`.

### frontend/src/components/sprints/primitives.tsx
**Purpose:** Sprint primitives.
**Reviewed lines:** 221.

#### Issues
- 🟡 MED line 62: `Math.round((sprint.metrics.storyPointsDone / sprint.metrics.storyPointsTotal) * 100)` — when `storyPointsTotal === 0`, this is `NaN`. The progress bar then renders zero, but the labels show `NaN%`.
- 🟡 MED line 89: `Math.max(1, Math.ceil((new Date(sprint.endDate).getTime() - Date.now()) / 86_400_000))` — when `endDate` is unparseable (empty string), `getTime()` returns `NaN`, and the result is `Math.max(1, NaN) → NaN`. Show "—" instead.

### frontend/src/components/sprints/charts.tsx
**Purpose:** Burndown + velocity charts.
**Reviewed lines:** 129.

#### Issues
- 🟡 MED line 67: legend background `rgba(255,255,255,0.85)` is hard-coded white — invisible in dark mode. Replace with `var(--con-surface)`.

### frontend/src/components/sprints/MigrationMappingCanvas.tsx
**Purpose:** React-Flow render.
**Reviewed lines:** 100.

#### Issues
- 🟡 MED line 61-62: `labelStyle: { fill: "var(--con-err)" }` — all edge labels render in error red regardless of edge status. Likely intentional ("blocked edge label") but visually misleading on completed edges.
- 🔵 LOW line 73-78: `fitView` runs only on mount; once nodes update, the view does not refit. If the user receives new nodes via SSE, they'd silently appear off-screen.

### frontend/src/components/sprints/MappingNode.tsx, SprintKanbanBoard.tsx
**Reviewed lines:** 67 + 263.

#### Issues
- 🟠 HIGH (SprintKanbanBoard.tsx line 237-249): `onClick` is attached to the same element as drag listeners. The author's workaround (`if (!drag.isDragging) onClick?.()`) is fragile — `isDragging` toggles right before `onClick` fires, so on a fast click-without-drag the click is sometimes swallowed. Use dnd-kit's `useSortable` with `useSensors({ activationConstraint: { delay: 200, tolerance: 5 }})`.
- 🟡 MED line 191-192: `style.background = "var(--con-brand-soft,var(--con-bg-2))"` is a CSS var fallback that **only works if** `--con-brand-soft` is defined; otherwise the fallback is `--con-bg-2`. Looks correct, but worth checking globals.css ships both.

### frontend/src/components/icons/AppIcon.tsx, LLMIcon.tsx, AgentIcon.tsx
**Reviewed lines:** 145 + 123 + 81.

#### Issues
- 🟡 MED (AppIcon.tsx line 29-42): `import * as si from "simple-icons"` then casting to `Record<string, SimpleIcon>` — pulls **the entire simple-icons library** into the bundle. Per their npm size, that's 2-3 MB of icons even though we use 12. Use the per-icon imports: `import { siSnowflake } from "simple-icons/icons/snowflake"`. Big bundle win.
- 🟡 MED (LLMIcon.tsx line 11): same `import * as si` problem.
- 🔵 LOW (AgentIcon.tsx line 12-21): every `react-icons/md` import causes a tree-shake fail on some bundlers. Verify with `next build` analyze.

### frontend/src/components/website/WebsiteNav.tsx, WebsiteFooter.tsx
**Reviewed lines:** 56 + 57.

#### Issues
- 🔵 LOW: `"Star · 2.4k"` is hard-coded. Either fetch live from GitHub API or drop the count.

### frontend/src/components/ThemeProvider.tsx
**Purpose:** Tweaks hydration + sync.
**Reviewed lines:** 106.

#### Issues
- 🟡 MED line 36-38: `useEffect` watches the entire Zustand `state` object — every Zustand `set()` produces a new object, so this fires on every change (which is the intent). Fine, but combined with the debounced sync below it does mean a rapid color-picker drag pushes 60+ state objects through `applyTweaksToDocument`. The function is cheap; OK.
- 🟡 MED line 72-94: debounced sync stores `lastSyncedRef` as JSON string — comparing JSON strings of objects with the same shape works because keys are inserted in the same order. If `hydrateFromServer` ever reorders keys, the diff check fires spuriously. Use a structural compare.

### frontend/src/components/ThemeToggle.tsx
**Purpose:** Old emoji-cycle theme toggle.
**Reviewed lines:** 37.

#### Issues
- 🔵 LOW: **dead code.** No page imports this; `useTweaks` superseded `getStoredTheme/setStoredTheme`. Delete.

### frontend/src/components/TweaksPanel.tsx
**Purpose:** Quick-access tweaks drawer.
**Reviewed lines:** 240.

#### Issues
- 🟠 HIGH line 51-56: drawer backdrop is a `<button>` (line 53) — this is *only* keyboard accessible because the element happens to be a button. But it has no `aria-modal`, no `role="dialog"` on the `<aside>`, no focus trap (only Esc-to-close on line 39-46). Screen readers and keyboard-only users can tab right out of the drawer.
- 🔵 LOW: also no `aria-label` on the panel itself.

### frontend/src/components/ArtifactDiff.tsx
**Purpose:** Naive line diff.
**Reviewed lines:** 117.

#### Issues
- 🟠 HIGH line 11-46: the algorithm is **not** Myers diff despite the comment saying "Myers-lite". It walks both arrays in lockstep, marking every mismatched line as `removed` + `added`. This produces *terrible* diffs for shifted code (e.g. inserting one line at the top reports every subsequent line as changed). Use `diff` or `fast-diff` library.
- 🟡 MED line 18-19: builds `oldSet`/`newSet` from string lines but never uses them.

### frontend/src/features/developer-workspace/DiffViewer.tsx, VersionHistoryDrawer.tsx, ApprovalModal.tsx
**Reviewed lines:** 48 + 36 + 30.

#### Issues
- 🟡 MED: these three components are an **older parallel implementation** of pieces of the workspace IDE. Today nothing imports them (verified via the page-tree above). Delete to remove dead code.
- 🟠 HIGH (ApprovalModal.tsx line 18, 23): uses `document.getElementById("approval-notes")` to read textarea content. This breaks if the modal is mounted twice (collision on ID), bypasses React state, and is the canonical "smell" of unmanaged React. Use a controlled `useState`.

### frontend/src/lib/auth-context.tsx
**Purpose:** Auth context.
**Reviewed lines:** 102.

#### Issues
- 🟠 HIGH line 32-47: the bootstrap `useEffect` runs only once at mount. If the token in `localStorage` expires while the app is open, the user keeps making 401-returning requests with no logout. Add token-expiry handling (decode JWT exp, schedule logout).
- 🟠 HIGH line 60-62: same bug as `login/page.tsx` — `setUser({ email, name: email.split("@")[0] })` creates a fake name. The bootstrap path at line 32-47 calls `/auth/me` and uses the real name; the login path doesn't. Convergence: have `login()` also call `/auth/me` post-success.
- 🟡 MED line 33: `localStorage.getItem` runs on first render. If running SSR (which Next does in dev), this throws — but it's wrapped in `useEffect` so it runs client-only. OK. Note that there's no `try/catch` for browsers with disabled localStorage (private mode in some browsers).
- 🟡 MED line 24: `API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"` — defined six times across the codebase (auth-context, use-api, api/client, dashboard/page, projects/page, projects/[id]/page, projects/new/page, projects/[id]/agents, validation/page is via library, etc.). Move to a single `src/lib/config.ts` export.

### frontend/src/lib/use-api.ts
**Purpose:** React hook for fetch with token.
**Reviewed lines:** 52.

#### Issues
- 🟡 MED line 26-30: `handleResponse` doesn't handle 401 — the error message becomes "HTTP 401" without triggering a logout. Add a side-effect to call `logout()` on 401.
- 🔵 LOW: `useApi()` is invoked on every render of pages that consume it; the returned object is a new identity each time, defeating any memoization. Wrap with `useMemo`.

### frontend/src/lib/api/client.ts
**Purpose:** Legacy `apiGet`/`apiPost` helpers.
**Reviewed lines:** 20.

#### Issues
- 🔵 LOW: **dead code.** No file imports `apiGet` or `apiPost` (verified via grep). Delete.

### frontend/src/lib/query-client.ts
**Purpose:** Singleton React-Query client.
**Reviewed lines:** 12.

#### Issues
- 🔵 LOW line 6-9: only sets `staleTime`, `retry`, `refetchOnWindowFocus`. No `cacheTime`, no `gcTime` (TanStack-Query v5 renamed `cacheTime` → `gcTime`). Tune for app: SSE-driven views shouldn't cache stale snapshots aggressively.

### frontend/src/lib/store.ts
**Purpose:** Zustand global app state.
**Reviewed lines:** 23.

#### Issues
- 🔵 LOW: `useAppStore` exposes `activeProjectId` and `sidebarCollapsed` — **neither is read anywhere** in the codebase (verified via grep). The sidebar doesn't collapse, the project context is implicit in the URL. Delete the store or wire it up.

### frontend/src/lib/theme-store.ts
**Purpose:** Tweaks store + DOM applier.
**Reviewed lines:** 154.

#### Issues
- 🔵 LOW line 110: `window.matchMedia(...)` runs in `resolveTheme` — but `applyTweaksToDocument` is guarded by `document === undefined`. SSR safe. Good.
- 🔵 LOW line 134-152: dark-mode branch *removes* the property so the dark-mode CSS picks defaults. That means dark mode ignores the user's chosen primary color — silent design decision. Consider deriving a dark-mode-adjusted version of the color instead.

### frontend/src/lib/theme.ts
**Purpose:** Legacy theme helpers.
**Reviewed lines:** 24.

#### Issues
- 🔵 LOW: superseded by `theme-store.ts`. Only `components/ThemeToggle.tsx` imports it, and ThemeToggle is itself dead. Delete both.

### frontend/src/lib/utils.ts
**Purpose:** Class merge + formatters + status tone.
**Reviewed lines:** 59.

#### Issues
- 🔵 LOW line 33-58: `statusTone` returns `{bg,fg,dot}` of Tailwind class strings, but `StatusBadge.tsx` (which fills a similar role) returns `Chip tone="..."` enums. The two systems coexist — `statusTone` for legacy callers, `StatusBadge.map` for the chip. Consolidate.

### frontend/src/lib/api-types.ts
**Purpose:** Hand-mirrored OpenAPI types.
**Reviewed lines:** 387.

#### Issues
- 🟠 HIGH line 1-4: file comment says "auto-generated, regenerate with `npm run generate:types`" — but it's hand-maintained today (visible from the formatting). The script in `package.json` line 11 points to `../backend/openapi.json` which **doesn't necessarily exist on a fresh checkout**. Update or remove the comment.
- 🟡 MED line 67-83: `ProjectResponse` lacks fields used by the actual pages (`source_system`, `target_system`, `owner_name`, `risk_score`, `validation_pct`, `recon_pct`, `table_count`, `phase`, `environments`, `updated_at`). The pages define their own `APIProject` interface and ignore this file.

### frontend/src/lib/queries/projects.ts, llm-providers.ts
**Reviewed lines:** 57 + 72.

#### Issues
- 🔵 LOW: only two of the dozens of `fetch`-based pages have been migrated to React-Query. Roll out across all pages or document the deprecation.

### frontend/src/lib/sprints/types.ts
**Purpose:** Sprint domain types.
**Reviewed lines:** 270.

#### Issues
- None — well-organized and consistent.

### frontend/src/lib/sprints/api.ts
**Purpose:** Sprint API client + SSE.
**Reviewed lines:** 458.

#### Issues
- 🔴 CRITICAL line 441: `?token=${encodeURIComponent(token)}` — JWT in URL query string. See execution page review. The comment acknowledges the trade-off but the architecture should fix it.
- 🟠 HIGH line 41: `if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);` — every page that calls `fetchX` then `.catch(() => setX([]))` swallows this error. No retry, no banner, no telemetry. At least log to console.
- 🟡 MED line 28-43: `req<T>` returns `res.json()` cast to `Promise<T>` without validation. If the backend response shape drifts, the adapter functions (`*FromWire`) will silently produce broken objects.
- 🔵 LOW line 443-454: parses each SSE frame inside a try/catch and ignores malformed — no telemetry on how often this happens.

### frontend/src/lib/sprints/index.ts
**Purpose:** Sprint barrel export.
**Reviewed lines:** 3.

#### Issues
- None.

### frontend/src/types/css.d.ts
**Purpose:** CSS module shim.
**Reviewed lines:** 4.

#### Issues
- 🔵 LOW: no CSS modules are actually used (the codebase uses Tailwind globals only). Dead.

---

## 3. Cross-cutting findings

### 3.1 Demo data shipped behind real shells
A consistent and serious pattern: **at least 9 pages render hard-coded mock data inside fully-styled `<AppShell>` containers** with no "this is demo data" affordance: `dashboard`, `projects/[id]/agents`, `projects/[id]/developer-workspace`, `developer-workspace` (no-id), `agents`, `validation`, parts of `admin/page.tsx`. Two admin pages (`users`, `audit-logs`) **silently fall back to mock demo data** when the API returns an empty list — a fresh deployment of Helix shows fictional "Avery Johnson" as a real admin user. This is the single highest-impact issue across the codebase.

### 3.2 Two parallel server-state systems
React-Query is set up but used only for `projects` and `llm-providers` queries. Everything else (Sprints, admin, validation, reconciliation, project detail, settings, etc.) uses raw `useEffect + fetch`. The result: inconsistent caching, no automatic refetch-on-window-focus (well, it's disabled globally — but no refetch-on-mutation invalidation either), and lots of duplicated boilerplate. Adopt React-Query everywhere or remove it.

### 3.3 Token in query string / localStorage
JWTs are stored in `localStorage` (XSS exfiltration risk) and passed via URL query strings to SSE (leaks to proxy logs / browser history). For an enterprise migration platform with audit-trail and SOC 2 ambitions, this is a notable security gap.

### 3.4 Dead buttons / dead state / dead components
- Sidebar `WorkspaceSwitcher`, `SearchTrigger` (⌘K hint), `UserFooter` (hard-coded user) — none functional.
- Topbar Notifications + Ask Helix — dead.
- Project detail page `setError` declared but never set.
- `ThemeToggle.tsx`, `lib/theme.ts`, `lib/api/client.ts`, `lib/store.ts` — dead code.
- `features/developer-workspace/*` — three orphan components.
- Dashboard "All projects" / "Manage" buttons — dead.

### 3.5 Mobile responsiveness is uneven
Multiple pages use unconditional `grid-cols-5`, `grid-cols-6`, fixed pixel SVG widths (1100, 720). The sidebar disappears at <lg but the 232px column reserves space anyway. There is **no mobile navigation pattern at all** — no hamburger, no drawer. The app is desktop-only in practice.

### 3.6 Accessibility gaps
Common to every modal in the codebase (TweaksPanel, ConnectModal, NewSprintModal, NewTaskModal, approval modals):
- No `role="dialog"` / `aria-modal`.
- No focus trap.
- Esc closes; clicking outside closes; but tab can leave.
- The drawer backdrop is sometimes a `<button>`, sometimes a `<div>` with handler.

Other recurring:
- Tables lack `<caption>` / `aria-label`.
- "Rows are clickable" hover affordance, but only one cell is the actual link.
- Disabled `<input>` used to display read-only values (skipped by screen readers).
- Risk-matrix and heatmap have no axis labels in markup.

### 3.7 Inconsistent component patterns
- Three Settings-page Toggle implementations, two AgentIcon naming conventions ("Mary" vs "bmad-agent-analyst"), two `KEYLESS_PROVIDERS` sets that disagree about `local`, six copies of `API_BASE`, three "developer workspace" pages with different layouts.
- `Chip.tsx` keeps legacy tone aliases (`indigo` → `brand`) — fine, but the codebase uses both, often within the same file.

### 3.8 Design-token leakage
Hundreds of inline `style={{}}` declarations with hex literals (`#6366F1`, `#4F46E5`, `rgba(79,70,229,0.08)`). These don't update when the tweaks panel changes the primary color. The `con-*` token system is great but underused inside the page bodies (`setup/first-admin`, `agents`, `connectors`, `developer-workspace` are the worst offenders).

### 3.9 Bundle size hotspots
- `simple-icons` and `react-icons` imported via `import * as`. Both packages do not tree-shake well via star import — every available icon ships. AppIcon, LLMIcon, AgentIcon together import the entire libraries.
- `reactflow` is loaded on multiple sprint pages eagerly. Lazy-load via `dynamic(() => import('reactflow'), { ssr: false })`.
- Marketing landing page (`app/page.tsx`) is 593 lines with deep `lucide-react` icon dependencies — first-paint hit for visitors who never use the console.

### 3.10 Error handling is silent
Across most pages, the pattern is:
```ts
fetch(...).then(r => r.ok ? r.json() : null).then(setX).catch(() => setX([]))
```
Failed requests produce an empty list with no banner, no toast, no console.error. Users cannot distinguish "no data yet" from "API is down".

### 3.11 No tests visible
There's a `playwright.config.ts` and an `e2e/` directory but no unit tests for the heavily-branched modal logic (`setup/first-admin`, `connectors` modal, kanban drag handler, optimistic approval). High-risk for regressions during the rewrite from mock-data to real-API.

### 3.12 Tweaks Panel coverage
`TweaksPanel` writes 5 properties to the store; `ThemeProvider` applies them. Two never reach dark mode (primary color, surface tint). Dark mode in general is implemented as a class toggle but **not tested** — no dark-mode-specific tokens for the major surfaces in `tailwind.config.ts`.

---

## 4. Severity summary

| Severity | Count |
|---|---|
| CRITICAL | 14 |
| HIGH     | 25 |
| MED      | 89 |
| LOW      | 60 |

---

## 5. Top 10 prioritized fixes

1. **`frontend/src/app/admin/users/page.tsx:44` + `audit-logs/page.tsx:42` — replace `data = users.length > 0 ? users : DEMO` with a real empty state.** Production users currently see fictional admin users / audit entries. (1 line each, immediate.)

2. **`frontend/src/lib/sprints/api.ts:441` — stop passing JWT in EventSource URL query string.** Implement a same-origin cookie or short-lived SSE-token endpoint. Affects `sprints/execution/page.tsx`.

3. **`frontend/src/components/layout/Sidebar.tsx:140-151` — wire `UserFooter` to `useAuth().user`.** Today every Helix deployment shows "Avery Johnson · Platform Admin" in the sidebar.

4. **`frontend/src/app/setup/first-admin/page.tsx:329` — replace direct `localStorage.setItem` after first-admin POST with `setupFirstAdmin()` from `AuthContext`.** Wizard's intermediate state currently bypasses the AuthContext.

5. **`frontend/src/app/dashboard/page.tsx` + `agents/page.tsx` + `validation/page.tsx` + `projects/[id]/agents/page.tsx` + `projects/[id]/developer-workspace/page.tsx` + `developer-workspace/page.tsx` — add an "Demo data" banner or feature-flag-gate these pages.** Six pages render fully-styled mock data with no signal.

6. **`frontend/src/components/icons/AppIcon.tsx:13` + `LLMIcon.tsx:11` — switch from `import * as si from "simple-icons"` to per-icon imports.** Removes 2-3 MB of unused icons from the bundle.

7. **`frontend/src/app/admin/system-health/page.tsx:28` — fix the `components` shape.** Backend returns `Record<string, HealthComponent>`, frontend assumes `Array<ComponentStatus>`. Page currently renders nothing.

8. **`frontend/src/lib/auth-context.tsx:60-62` + `login/page.tsx` — call `/auth/me` after login to fetch the real user name.** Today the name is derived from `email.split("@")[0]`.

9. **`frontend/src/app/connectors/page.tsx:415-423` — replace the `setTimeout` / `Math.random()` connection-test simulator with a real backend call.** Users currently see fictional pass/fail outcomes when testing production credentials.

10. **`frontend/src/components/TweaksPanel.tsx` + every other modal — add focus trap + `role="dialog"` + `aria-modal`.** Standardize via a `<Modal>` primitive in `components/ui/`.

---

## 6. Architecture suggestions

### 6.1 Adopt React-Query everywhere
Remove every `useEffect(() => fetch(...))` and replace with `useQuery` / `useMutation`. Standardize an `useApi()` -> mutationFn pattern. Centralize 401 handling (auto-logout) in the QueryClient defaults. The `lib/queries/` folder is the right structure — flesh it out for sprints, validation, recon, admin, etc.

### 6.2 Carve out a `(marketing)` and `(app)` route group
Marketing (`/`, `/login`, `/setup/*`) doesn't need the AppShell, the auth context, the React-Query client, or the tweaks store. Use Next's route groups to split bundles:
```
app/(marketing)/{page,layout}.tsx     ← lightweight
app/(app)/{layout,page}.tsx           ← Providers + AppShell
```

### 6.3 Build a `<Modal>` primitive
Every modal in the codebase reimplements the same backdrop + Esc + close-on-outside-click logic, all subtly different and all with missing a11y. One headless `Modal` (or `Dialog`) with focus trap (e.g. `@radix-ui/react-dialog` is the de-facto choice) deletes ~600 lines.

### 6.4 Consolidate "API_BASE"
Six declarations. One `src/lib/config.ts`:
```ts
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```

### 6.5 Reusable empty-state pages
`/files`, `/plugins`, `/reports`, `/templates` are identical EmptyState pages. Build a `<ComingSoonPage feature="files" />` and route each placeholder through it.

### 6.6 Split "developer-workspace" into one canonical implementation
Three pages today: `/developer-workspace` (mock IDE), `/developer-workspace/[id]` (real AI review), `/projects/[id]/developer-workspace` (project mock). Pick one shape (probably `/projects/[id]/developer-workspace/[artifactId]`) and delete the rest. The `features/developer-workspace/*` orphans get deleted in the same pass.

### 6.7 Migrate types to OpenAPI codegen
`lib/api-types.ts` is hand-maintained and already out of sync with what pages assume (`ProjectResponse` lacks `source_system` etc.). Wire up `openapi-typescript` to run on backend build, commit the generated file, and have pages import from it instead of re-declaring shape types inline.

### 6.8 Lazy-load heavy panels
- `ReactFlow` (used in 3 pages) → `dynamic(() => import('reactflow'), { ssr: false })`.
- `MigrationMappingCanvas` + `SprintKanbanBoard` → dynamic.
- Marketing landing page diagrams → server component.

### 6.9 Add an auth hook layer
- `useAuthenticatedFetch()` returns a `fetch` wrapper that auto-injects the token and handles 401 by logging out and redirecting to `/login`.
- `useRequireAuth()` redirects to `/login` if `token === null` (consistently across pages — many pages today render under an unauthenticated state and silently no-op their fetches).

### 6.10 Mobile shell
The app has no mobile navigation. A hamburger that opens the `<Sidebar>` as a drawer on small screens is a 50-line addition with high impact. Without it, the sidebar's 232px column reserves space on every viewport, breaking the layout on phones.

### 6.11 Page-level error boundaries
Add `app/(app)/error.tsx` plus `app/(app)/loading.tsx` so React Suspense-friendly data flow can replace the manual `loading` flags every page maintains.

### 6.12 Dark mode parity
Run a dark-mode audit pass. Today, `applyTweaksToDocument` strips the brand color and surface tint when in dark mode (theme-store.ts line 138, 148). Define explicit dark-mode CSS variables in `globals.css` (which I didn't read, but the symptom is the only dark-mode behavior is "remove the var override"). Plumb a real dark palette.

### 6.13 Telemetry / observability
Every silent `.catch(() => setX([]))` is a missed monitoring signal. Add a thin `reportError(err, context)` shim that pages call from catches; in dev it `console.error`s, in prod it could ship to Sentry/PostHog.

### 6.14 Componentize sprint primitives further
Sprint pages all reimplement the empty-state "Run seed" pattern (with `handleSeed` + `seeding` state + `seedSprints`). Lift this into a `<SprintEmptyState projectId={…} />` component used by every sprint sub-route.
