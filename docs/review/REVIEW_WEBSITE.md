# Website Code Review

> Generated 2026-05-26. Scope: `website/` public marketing site (Vite + React 18 + TypeScript + Tailwind 3, React Router v6).

Legend: CRITICAL, HIGH, MED, LOW. Severity emojis: red CRITICAL, orange HIGH, yellow MED, blue LOW.

---

## 1. High-level architecture

The Helix marketing website is a **single-page Vite/React application**
deployed as a static bundle to Hostinger (Apache/LiteSpeed). It is
intentionally decoupled from the authenticated product (`frontend/`,
Next.js) and from the backend — no API calls, no data fetches at
runtime.

### 1.1 Entry + routing

- `index.html` is the static shell that ships `<meta>` SEO, JSON-LD
  schema, Open Graph + Twitter card tags, and a hand-crafted CSP, then
  loads `src/main.tsx` as an ES module.
- `src/main.tsx` mounts `<App/>` inside `<React.StrictMode>` and a
  top-level `<BrowserRouter>`.
- `src/App.tsx` declares the five routes:
  - `/`                — `HomePage`
  - `/features`        — `FeaturesPage`
  - `/architecture`    — `ArchitecturePage`
  - `/docs/*`          — `DocsPage` (nested `<Routes>` with `index`
    + `:id`)
  - `/open-source`     — `OpenSourcePage`
  - `*`                — `<Navigate to="/" replace />` (catch-all
    redirect; **no client-side 404 page** is rendered).
- A `/demo` React route was deliberately removed (App.tsx top comment).
  Visitors now follow `STATIC_DEMO_URL` (`/helix-console-demo.html`) —
  the 1.5 MB pre-rendered Figma-bundler HTML mock in `public/`.

### 1.2 Data layer

The site has **two content modules and no API**:

- `src/data/site-content.ts` — `SITE`, `NAV`, `FOOTER`, `HERO_CTAS`,
  `DOCKER_INSTALL`, `FEATURES`, `AGENTS`, `PIPELINE_NODES`,
  `CONNECTORS`, `FEATURE_MAP_CHAIN`, `FEATURE_LAYERS`, `ROADMAP`,
  `CONTENT_RULES_DISCLOSURE`, `STATIC_DEMO_URL`. Single source of
  truth for hero copy and marketing numbers.
- `src/data/docs-content.ts` — typed `DocEntry[]` (21 entries across
  9 `DOC_CATEGORIES`) plus helpers `findDoc(id)` and
  `docsByCategory()`. Every documentation page is data, not a per-page
  component.

### 1.3 Component layers

- **layout/** — `WebsiteLayout` (shell), `Navbar` (sticky, blurred,
  mobile accordion), `Footer`, `BrandMark` (SVG monogram),
  `SectionHeader` (eyebrow + title + description).
- **landing/** — `Hero`, `Features`, `Architecture`, `FeatureMap`,
  `Agents`, `Connectors`, `ValidationRecon`, `DeveloperWorkspace`,
  `DockerInstall`, `Roadmap`, `CTA`. Each is a content-driven
  pure-presentational section.
- **docs/** — `DocsLayout` (sticky sidebar on `md+`, accordion below
  `md`), `DocsSidebar` (category-grouped nav with built-in search),
  `DocsSearch` (text input), `DocsPage` (article renderer),
  `FeatureDocCard` (grid card on docs index).
- **pages/** — thin wrappers that compose landing sections.

### 1.4 Styling

- Tailwind 3 with a custom palette (`ink`, `surface`, `brand`,
  `cyan`), custom fonts (`Space Grotesk` + `IBM Plex Mono` from
  Google Fonts), and a few utility classes in `src/styles.css`
  (`eyebrow`, `container-tight`, `focus-ring`, `gradient-text`,
  `scroll-fade-x`, `section-fade-in`).
- Body background uses two radial gradients + a linear fallback;
  `grid-faint-bg` provides the subtle dot grid.

### 1.5 Static asset / deploy pipeline

- `public/` is copied verbatim into `dist/` by Vite (per Vite
  convention). This is how `og-image.svg`, `favicon.svg`,
  `robots.txt`, `sitemap.xml`, `.well-known/security.txt`, and the
  1.5 MB `helix-console-demo.html` ship.
- `_headers` is the Cloudflare Pages / Netlify-style header file.
- `.htaccess` is the Apache/LiteSpeed equivalent for Hostinger and is
  the one **explicitly copied** by `scripts/copy-hostinger-files.mjs`
  (the `build:hostinger` script). Vite would copy it automatically
  in newer versions; the script exists because the `.` prefix used to
  be filtered out.
- Build emits two artifacts in `dist/assets/`:
  `index-*.js` ≈ 255 KB and `index-*.css` ≈ 25 KB. No code splitting
  is configured.

### 1.6 What's missing structurally

- No service worker, no PWA manifest, no offline fallback.
- No analytics. (Consistent with the "no telemetry phone-home"
  brand promise.)
- No MDX, no markdown loader — docs content is plain TS strings in a
  single file.
- No image pipeline — the only images are SVG.
- No test runner — `package.json` has no `test` script.
- No linter / Prettier in dev dependencies. TypeScript strict mode is
  the only static check.

---

## 2. File-by-file review

### 2.1 `website/index.html`

🔵 LOW: Line 7 — `<title>` is "Helix - Open-source AI-powered
migration and validation platform" (95 chars). Within the 50-60
recommended search-result width budget, but the most informative
keyword ("AI-powered migration") sits at char ~30 — fine for SEO,
just verify Google's truncation point.

🟡 MED: Lines 8-9 — `description` is 173 chars; tolerable but
slightly above Google's 155 char typical snippet. Consider trimming
to ≤ 160.

🔵 LOW: Line 11 — `<meta name="keywords">` is widely ignored by
modern search engines. Harmless but dead code.

🟠 HIGH: Line 16 — **`<meta http-equiv="Content-Security-Policy">`**:
- `script-src 'self'` is admirable but the Google Fonts
  preconnect on line 30-31 implies you want fonts from a third-party
  origin. The stylesheet itself is loaded from
  `https://fonts.googleapis.com/...` (line 32) — and that is **not in
  `style-src`** as `https://fonts.googleapis.com`? Actually it is.
  However: `'unsafe-inline'` is allowed in `style-src` to permit
  Tailwind-injected styles, which materially weakens CSP. Document
  this trade-off or migrate to nonce/hash-based.
- No `script-src-elem` / `script-src-attr` split. Modern bots
  (e.g. Cloudflare bot management) prefer the granular form.
- No `report-uri` / `report-to` for violation reporting.
- `connect-src 'self'` blocks any future call to `api.helix.datainteg.io`
  — fine for a static site, but worth noting if a contact-form
  endpoint is added later.

🔵 LOW: Line 14 — `theme-color #4F46E5` matches brand-600. Good.

🟡 MED: Line 17 — `og:title` is just "Helix"; consider matching the
HTML `<title>` for richer link previews.

🟡 MED: Line 23, 27 — Both `og:image` and `twitter:image` reference
**SVG** (`og-image.svg`). Facebook's OG parser **rejects SVG** silently
in many cases and most LinkedIn/Twitter previewers prefer PNG or JPG.
Recommend rasterising og-image at 1200×630 PNG (and keeping the SVG
as the source).

🔵 LOW: Line 24-25 — `og:image:width/height` declared. Good.

🟡 MED: Line 26 — `twitter:card` is `summary_large_image` but
`twitter:site` and `twitter:creator` are missing.

🔵 LOW: Line 32 — Two Space Grotesk weights and two IBM Plex Mono
weights are loaded; only the weights actually used in `styles.css`
(400, 500, 600, 700 / 400, 500) — verify all are needed. Hero uses
`font-semibold` (600), most copy is 400-500, the eyebrows use 500.
700 may be unused. Audit and trim to shave ~30 KB off font payload.

🟠 HIGH: Line 32 — Font stylesheet uses `display=swap` which is good
for FOIT prevention, but there is **no `<link rel="preload">`** for
the woff2 font assets themselves. On first paint the browser does
the CSS round-trip + font round-trip serially. Cost: ~150-300 ms LCP.

🔵 LOW: Lines 33-54 — JSON-LD is well-formed `SoftwareApplication`,
but missing `offers` (free), `aggregateRating`, `softwareVersion`. If
you want a richer Google knowledge panel, add at least `softwareVersion`
+ `datePublished`.

🔵 LOW: Line 57 — `<div id="root"></div>` has no SSR fallback /
loading skeleton / `<noscript>` notice. For visitors with JS
disabled, the entire page is blank.

🟡 MED: Missing favicon variants — no apple-touch-icon, no
`manifest.json`. iOS bookmarks will use the page screenshot.

🔵 LOW: Missing `<html lang="en-US">` (currently `lang="en"`). Either
is valid; `en-US` is slightly better for Hreflang signalling if you
ever ship localized pages.

---

### 2.2 `website/package.json`

🔵 LOW: Line 5 — `"type": "module"` is correct given Vite + ESM.

🟡 MED: Line 7-12 — `"scripts"` has no `lint`, `format`, `test`,
`typecheck`. `build` already runs `tsc -b` so typecheck is implicit at
build, but devs working incrementally lose feedback. Add at minimum
`"typecheck": "tsc -b --noEmit"`.

🔵 LOW: Lines 13-18 — Dependencies are lean (just React, RR DOM,
lucide-react). Good.

🟠 HIGH: Line 14 — `lucide-react@^0.400.0` is pinned to a caret. The
project imports 24+ icons — verify your bundler is tree-shaking
correctly (Vite + Rollup does this by default for the ESM build of
lucide). 255 KB JS bundle suggests it's working, but worth checking
with `vite build --report` once.

🔵 LOW: No `engines.npm`, only `engines.node`. Add `npm` minimum to
avoid lockfile drift.

🔵 LOW: No `private: true` would let you publish accidentally;
`"private": true` is set on line 4 — good.

🔵 LOW: No `homepage` field — not required for a Vite SPA, but useful
for tooling.

🟡 MED: `package-lock.json` is committed (good), but the project has
no `.npmrc` pinning the registry — supply-chain hardening would be
`save-exact=true` to prevent semver-range drift.

---

### 2.3 `website/vite.config.ts`

🔵 LOW: Lines 7-16 — Minimal config. `outDir: "dist"`,
`sourcemap: false`. Sourcemaps off in production is fine; you may
want them for staging / preview deploys (`sourcemap: 'hidden'`
ships the .map but doesn't link it in the bundle).

🟡 MED: No `build.rollupOptions.output.manualChunks`. With React +
React Router + Lucide all in one 255 KB chunk, the entire app
re-downloads on any code change. Splitting `vendor` (react,
react-dom, react-router-dom) from `app` would drop cache invalidation
cost.

🟡 MED: No CSS code-splitting hint, no `chunkSizeWarningLimit`,
no `target: 'es2020'` override (default for `@vitejs/plugin-react` is
`baseline-widely-available` in newer Vite which may transpile away
modern features).

🔵 LOW: `server.host: true` exposes dev server to LAN. Fine for
collaborators on the same network; mention in README.

🔵 LOW: Line 5 — Comment uses an `â€"` character (mojibake — this
file was saved as Windows-1252 and read as UTF-8 somewhere). Cosmetic.

---

### 2.4 `website/tailwind.config.ts`

🔵 LOW: Line 4 — `content` glob `./src/**/*.{ts,tsx}` is correct.

🔵 LOW: Lines 12-17 — `ink` scale defines 5 stops (DEFAULT, 2, 3, 4,
5). The naming convention is custom; consider matching Tailwind's
50-900 scale to ease IDE autocomplete.

🟡 MED: Lines 24-31 — `brand` palette skips 200, 300, 400, 800. The
codebase uses `brand-50`, `brand-100`, `brand-600`, `brand-700`,
`brand-900` (and `brand-200` referenced in Features.tsx line 47 +
Roadmap.tsx line 23 + others). `brand-200` is missing from the
config — Tailwind will silently emit no class, falling back to no
border colour. Verify visual.

Verification: grepping `brand-200` shows it is referenced in 5+ files.
Tailwind 3 with arbitrary value mode might still resolve it, but
without an entry in `colors.brand` the class is **undefined** and the
border colour falls back to the browser default (`currentColor`).
This is likely the source of any "border looks subtle by accident"
issue.

🔵 LOW: Lines 32-43 — `cyan` palette is full 50-900 (one of the few
fully-stocked palettes). Good.

🔵 LOW: Lines 56-60 — `backgroundImage` defines `indigo-cyan`,
`soft-indigo`, `grid-faint`. `grid-faint` is also re-implemented in
`styles.css` as `.grid-faint-bg` — duplicated source of truth.

🔵 LOW: Lines 51-55 — `borderRadius` overrides `DEFAULT` to 10px (vs
Tailwind's default 4px). Anything using bare `rounded` now produces
10px corners; verify intentional.

🔵 LOW: Lines 45-50 — `boxShadow.hero` looks unused (grep for
`shadow-hero`).

Verification: `shadow-hero` is used in `CTA.tsx`. OK.

---

### 2.5 `website/tsconfig.json`

🔵 LOW: Lines 9, 11 — `allowImportingTsExtensions: true` + `noEmit:
true` is the modern Vite-style config. Good.

🟡 MED: Lines 15-16 — `noUnusedLocals: false`, `noUnusedParameters:
false`. Both turned off. This is permissive — combined with no ESLint
this means dead imports / unused destructured props can ship to
production. Consider flipping these on (`true`) at least in CI.

🔵 LOW: Line 17 — `noFallthroughCasesInSwitch: true` is good.

🔵 LOW: Line 14 — `strict: true` is on. Good.

🟡 MED: Missing `forceConsistentCasingInFileNames`, `noImplicitOverride`,
`exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`. Each closes
a class of latent bugs (especially `noUncheckedIndexedAccess` — paired
with `DOCS.find()` + `params.id` style code).

🔵 LOW: Line 22 — `references` to `tsconfig.node.json` is present
but the file was not loaded into this review. Verify it covers
`vite.config.ts` and `scripts/copy-hostinger-files.mjs`.

---

### 2.6 `website/postcss.config.js`

🔵 LOW: Standard 2-plugin config. Nothing to flag.

🟡 MED: Consider adding `cssnano` for prod (Vite's default minifier
is already lightning, but explicit cssnano gives finer control).

---

### 2.7 `website/scripts/copy-hostinger-files.mjs`

🔵 LOW: Single-purpose script that copies `public/.htaccess` to
`dist/.htaccess` post-build. Defensible because Vite 5 *does* copy
dot-prefixed files in `public/` by default — verify this script is
still needed (a quick `ls dist/` after `npm run build` would tell;
the dist listing shows `.htaccess` is already there).

🟡 MED: This script copies **only** `.htaccess` — but `public/` now
also contains `_headers`, `.well-known/security.txt`, `robots.txt`,
`sitemap.xml`. If the `.htaccess` copy is needed, then the others
might be needed too — verify they survive Vite's copy step. The
dist listing confirms they do. Script is **redundant** for Vite 5+.

🔵 LOW: Line 13-16 — Error message is human-friendly + non-zero exit.
Good.

🔵 LOW: No `// @ts-check` directive. Add for editor type hints.

---

### 2.8 `website/README.md`

🔵 LOW: Lines 33-62 — File-tree snippet mentions
`src/data/demo-data.ts` and `src/components/demo/` (DemoShell,
DemoSidebar) — but the **`/demo` route was removed** and neither
`demo-data.ts` nor the demo components exist in the current source
tree (verified via Glob). Outdated docs.

🟡 MED: Line 59 — Mentions `pages/DemoPage.tsx` which no longer
exists. Same issue.

🔵 LOW: Lines 66-69 — "Demo numbers / agents / projects | Edit
`src/data/demo-data.ts`" — broken instruction since the file is gone.

---

### 2.9 `website/src/main.tsx`

🔵 LOW: Standard React-18 + Router boot. Five lines of imports,
nine lines of mount. No issues.

🟡 MED: No `<HelmetProvider>` / no per-route `<title>` overrides. As
a result every route shares the home page's `<title>`. SEO-wise this
is bad — `/docs/installation` shouldn't have the same `<title>` as
`/`. Either add `react-helmet-async` or use a tiny custom hook.

🟡 MED: No `<ErrorBoundary>` wrapper. A single child throw nukes the
entire site. For a marketing page that's a worst-case "blank screen"
brand hit.

---

### 2.10 `website/src/App.tsx`

🔵 LOW: Line 22 — `<Route path="*" element={<Navigate to="/" replace />}`.
This **silently redirects** any unknown URL to home — which means
external linkers and bots see a 200 OK for any URL they construct.
Search engines may flag this as soft-404 behaviour. Render an
explicit 404 page instead, then `<Navigate>` only when intentional.

🟡 MED: No `<Suspense>` boundary; no `lazy()` imports. Every page
ships in the initial bundle. The 6 page components are small but
`Agents` + `FeatureMap` + `DeveloperWorkspace` are non-trivial.

🔵 LOW: Lines 10-11 — Helpful comment explaining the `/demo`
removal. Good.

---

### 2.11 `website/src/styles.css`

🔵 LOW: Lines 5-19 — Base reset is minimal. Good.

🟡 MED: Lines 9-13 — Two heavy radial-gradients on `<body>`. Repaint
cost on resize is non-trivial; mobile browsers may stutter. Profile
with DevTools paint-flashing.

🔵 LOW: Lines 22-29 — `.eyebrow` defined here AND inferred from
Tailwind `text-[11px]` patterns elsewhere; a few places use
`eyebrow text-[10px]` to override the base (Footer, FeatureDocCard).
Slightly inconsistent but OK.

🟡 MED: Line 30 — `.font-mono` is redefined despite Tailwind's
built-in `font-mono` utility. This **shadows** the Tailwind class.
Risk: any Tailwind purge that changes font-mono's stack won't apply
to this site, and Storybook/external tooling will see different
fallbacks. Delete this rule and let Tailwind's `font-mono` (which is
already mapped via `tailwind.config.ts` line 9 to `IBM Plex Mono`)
own it.

🔵 LOW: Lines 33-38 — `.grid-faint-bg` duplicates the
`backgroundImage.grid-faint` Tailwind entry. Pick one source of
truth.

🔵 LOW: Lines 45-47 — `.focus-ring` is fine but `focus-visible:` is
the modern pattern (already used). Verify older Safari support
(focus-visible has been in Safari ≥ 15.4 since 2022).

🔵 LOW: Lines 71-79 — `@keyframes fade-up` is simple and fine. The
0.6 s duration is slightly long for a hero (200-400 ms feels
snappier).

🔵 LOW: Lines 57-68 — `.scroll-fade-x` mask is clever and
mobile-only — nice touch.

🟡 MED: No `@media (prefers-reduced-motion: reduce)` override —
`fade-up` will animate even for users who have asked the OS to
disable motion. Add:

```css
@media (prefers-reduced-motion: reduce) {
  .section-fade-in { animation: none; }
}
```

---

### 2.12 `website/src/data/site-content.ts`

🔵 LOW: Lines 6-16 — `SITE` constants are sensible. `email:
"contact@datainteg.io"` matches `security.txt`. Good.

🟠 HIGH: Lines 114-127 — `CONNECTORS` array is **8 entries** but the
inline comment on line 114 calls them "8 shipped connectors +
extension point" — really it's 7 shipped connectors plus one Custom
Connector tile that is itself the extension point. The hero pill
("8 connectors", `Hero.tsx:71`) and the section subtitle
(`Connectors.tsx:10` — "Seven sources out of the box plus a small
Python adapter") **disagree**. Reconcile to either:
- "7 connectors + custom adapter" (subtitle wins, hero pill becomes
  "7 connectors").
- "8 connector slots" (hero wins, subtitle should match the array
  length).

🟡 MED: Lines 89-96 — `AGENTS` has 6 entries. `AGENT_COLORS` in
`Agents.tsx` has 6 entries. `PIPELINE_NODES` has 13 entries. The
*agent workflow* docs page (`docs-content.ts:125`) lists 13 pipeline
steps. **However** the doc starts with "Winston · project context"
whereas `PIPELINE_NODES[0]` is "Requirement Intake". Mild copy
drift — pick one wording.

🔵 LOW: Lines 51-55 — `HERO_CTAS.primary.external: true` is read by
nothing (Hero.tsx uses `target="_blank"` hard-coded). Dead property.

🔵 LOW: Lines 142-162 — `FEATURE_LAYERS` has 4 layers with 4 items
each — visually consistent and matches docs `product-overview`. Good.

🔵 LOW: Lines 164-169 — `ROADMAP` matches `docs-content.ts` roadmap
section. Good.

---

### 2.13 `website/src/data/docs-content.ts`

🔵 LOW: Lines 11-25 — `DocSection` + `DocEntry` interfaces are clean.

🟡 MED: Lines 27-37 — `DOC_CATEGORIES` is hard-coded; the
`docsByCategory()` helper trusts this list as the order. If an
author adds an entry with a new category, it silently won't render
in the sidebar (the empty-category short-circuit in
`DocsSidebar.tsx:54-55` skips it). Add a validation pass or change
`groupFiltered()` to derive categories from the data.

🔵 LOW: Line 39 — `DOCS: DocEntry[]` is the master array.
Currently 21 entries; that's roughly 12 KB of TS. Acceptable for
now; at 100+ entries this should migrate to MDX or a CMS.

🟠 HIGH: Lines 105-117 — `llm-provider-setup` lists 10 LLM
providers — but inside the bullet list says "OpenAI — gpt-5.5,
gpt-5-mini, gpt-realtime-2, gpt-5.5-thinking" and "Anthropic —
claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5" and "Google
Gemini API — gemini-3-pro/flash/flash-lite/omni". These model names
are aspirational and **likely wrong on launch day** — Helix's actual
runtime probably lists `gpt-4o`, `claude-3-5-sonnet`, `gemini-1.5-pro`
etc. Verify against `agents/runtime/providers/` and update before
press launch — otherwise a reviewer who tries `gpt-5.5` will see a
404 and lose trust.

🟡 MED: Lines 119-130 — `agent-workflow` content references nodes
that don't exactly match `PIPELINE_NODES` in site-content.ts (see
above). Single-source these.

🔵 LOW: Line 175 — "≥ 95%" uses an actual `≥` character; ensure file
is UTF-8 (it is, per the `≥` in the snippet).

🔵 LOW: Lines 309-321 — Helper functions `findDoc` + `docsByCategory`
are tight and used. Good.

🔵 LOW: Lines 165 — `docsByCategory` re-initialises buckets twice
(line 315 + 317 fallback). The second initialiser handles
categories not in `DOC_CATEGORIES` — fine.

---

### 2.14 `website/src/components/layout/WebsiteLayout.tsx`

🟠 HIGH: Line 9 — `<main className="flex-1">` has **no `id`** and no
`tabIndex={-1}`. There's no **"skip to main content" link** in the
header. Keyboard-only users have to tab through Navbar (≈ 8 items)
on every navigation. Add:

```tsx
<a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 ...">
  Skip to content
</a>
<main id="main" tabIndex={-1} className="flex-1">{children}</main>
```

🔵 LOW: Otherwise correct — semantic `<main>` + flex column shell.

---

### 2.15 `website/src/components/layout/SectionHeader.tsx`

🔵 LOW: Lines 11-15 — Single responsibility, clean prop interface.
Good.

🟡 MED: Line 9 — `align` only branches between "left" and "center"
visually, but `mx-auto` is appended for centre alignment without
removing `text-left`'s effect (the inner `text-left` becomes inert
because the parent does `text-center`). Cosmetic.

🔵 LOW: Line 13 — `<h2>` is hard-coded. SectionHeader is used by 6+
sections per page so multiple `<h2>` per page is fine — but the
hierarchy on `/` (`<h1>` in Hero, then many `<h2>` in sections) is
correct.

---

### 2.16 `website/src/components/layout/Navbar.tsx`

🔵 LOW: Lines 8-9 — Sticky top, blurred backdrop, z-40. Good.

🟡 MED: Line 9 — `<header>` is the wrapper; `<nav>` is on line 17.
Inside one `<header>`. Good semantics.

🔵 LOW: Lines 11-12 — `bg-white/72` is non-standard Tailwind; should
be `bg-white/75` or arbitrary `bg-white/[.72]`. As written, Tailwind
generates `bg-white/72` as an arbitrary class — verify it actually
emits something. If not, the navbar will lose its translucent backdrop.

Verification: Tailwind 3.3+ supports any integer 0-100 in the
`/N` opacity syntax (e.g. `bg-white/72`). OK.

🟡 MED: Lines 52-58 — Mobile menu toggle has no `aria-expanded`
binding. Add `aria-expanded={open}` so screen readers announce
state.

🔵 LOW: Lines 56-57 — `aria-label="Toggle menu"` is fine. Consider
"Open menu" / "Close menu" toggling on `open`.

🟠 HIGH: Lines 60-86 — Mobile menu is conditionally rendered
(`open && ...`) — meaning the DOM doesn't reserve space and the menu
**hides nothing** behind it. But on iOS Safari the **body scroll
locks** in the parent layout while the menu is open is missing —
users can scroll under the menu. Add `overflow: hidden` on body
toggle.

🔵 LOW: Lines 42-50 — Comment + CTA — fine.

🟡 MED: Lines 43-50 — "View demo" gradient CTA's `target="_blank"`
uses `rel="noreferrer"` (no explicit `noopener`). Modern browsers
imply `noopener` when `noreferrer` is set, but for older browsers
(Chrome < 88 on legacy embedded) add `noopener noreferrer`
explicitly across the site (see §3.2).

🔵 LOW: Lines 11 — `border-zinc-200/80` — fine, Tailwind
opacity modifier.

🔵 LOW: Lines 19-25 — `NavLink` active state via `({ isActive })`
function. Idiomatic.

🔵 LOW: No keyboard escape handler for the mobile menu (Esc should
close). Optional.

🔵 LOW: After clicking a mobile nav link, the menu closes (`onClick={() => setOpen(false)}`)
— good.

🟡 MED: There is **no logo link aria-label** — the `<Link to="/">`
wraps the BrandMark + word "Helix" but no `aria-label` so the SR
announces "Helix" link, which is OK because the visible text matches.

---

### 2.17 `website/src/components/layout/Footer.tsx`

🔵 LOW: Lines 8-9 — `<footer>` semantic root with top border. Good.

🔵 LOW: Lines 10-23 — Two-row grid layout, brand block + 3 link
columns. Good.

🔵 LOW: Line 17 — `Apache 2.0 | helix.datainteg.io` uses ASCII pipe
not en-dash. Consistent with mono-font monospaced look.

🔵 LOW: Line 25 — `(c)` instead of `©` — likely a deliberate choice
to dodge encoding issues. Either is fine. © renders better.

🔵 LOW: Lines 36-55 — `FooterColumn` helper component. Clean.

🟡 MED: Line 41-42 — External links use `target="_blank"` +
`rel="noreferrer"`. No `noopener`. Same theme as Navbar.

🔵 LOW: Line 44 — External link uses raw `<a>`; internal uses
`<Link>`. Correct.

🟡 MED: Footer has no contact email / no mailto link, despite
`SITE.email` existing. Surface this prominently for
inquiries; security.txt has it too.

---

### 2.18 `website/src/components/layout/BrandMark.tsx`

🔵 LOW: Lines 1-16 — Inline SVG monogram with linearGradient. Good.

🟡 MED: Line 6 — `<linearGradient id="helixGradient">` — **the same
gradient id is used in `favicon.svg`**. If BrandMark is mounted twice
on the page (it is — Navbar + Footer) the gradient definitions don't
collide because each `<svg>` is a separate document fragment. But
two BrandMarks on the page = two `<defs>` with the same ID. Browsers
will pick the first match; SVG referencing rules are scoped to the
nearest ancestor, so this *should* work. Safer: parameterise the id
or use a `useId()` hook.

🔵 LOW: Line 4 — `role="img"` + `aria-label="Helix logo"`. Good.

🔵 LOW: Line 12 — The H glyph path is hand-crafted. OK.

---

### 2.19 `website/src/components/landing/Hero.tsx`

🔵 LOW: Lines 1-6 — Imports are minimal.

🔵 LOW: Lines 8-18 — `onCopy` handler with `try/catch` (catches
permission-denied on iOS Safari, etc.). Good.

🟡 MED: Line 16 — `catch { /* no-op */ }` silently swallows. Add a
user-visible "Copied" / "Couldn't copy" state.

🔵 LOW: Lines 21-29 — Two layered background gradients +
grid-faint. Beautiful but expensive paint.

🔵 LOW: Lines 33-36 — `<h1>` with gradient-text span. Single `<h1>`
per page. Good.

🟡 MED: Line 36 — `<span className="gradient-text">` uses
`background-clip: text` + `color: transparent`. Older Edge (< 79)
and some screen-reader / forced-colours-mode environments will see
nothing. Provide a `forced-colors` media-query fallback:

```css
@media (forced-colors: active) {
  .gradient-text { color: CanvasText; }
}
```

🟠 HIGH: Lines 41-68 — Three CTAs (View demo, Read Docs, View
GitHub). The **GitHub label** is "View GitHub" which is awkward
phrasing — usually "Star on GitHub" or just "GitHub".

🔵 LOW: Line 71 — Pill array `["13-step pipeline", "10 LLM
providers", "8 connectors", "Self-hosted Apache 2.0"]` — see §3.6
for the **"8 connectors" vs "Seven sources"** consistency bug.

🔵 LOW: Lines 78-100 — Install-card UI: window-controls dots,
copy button, monospace pre. Good visual.

🔵 LOW: Line 98 — `whitespace-pre-wrap break-all md:whitespace-pre
md:break-normal` — mobile-friendly. Good.

🔵 LOW: No "What's new" / changelog teaser. Marketing-page nice-to-have.

🔵 LOW: Line 87 — `install · ~5 min` — claim. Realistic? OK if
benchmarked.

---

### 2.20 `website/src/components/landing/Features.tsx`

🔵 LOW: Lines 1-12 — Lucide icons are tree-shake-friendly named
imports. Good.

🔵 LOW: Lines 17-27 — `ICON_MAP` is an in-file string → component
map. Works; alternative would be passing the component reference
in `site-content.ts` directly, but that couples data to React.

🔵 LOW: Lines 37 — `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`.
Standard.

🔵 LOW: Lines 40 — `featured = i === 0` highlights the first
feature (BMAD pipeline). Good editorial choice; verify the
ordering is intentional, since changing FEATURES array order will
change which card is featured.

🟡 MED: Line 47 — Featured card uses `border-brand-200` which is
**not in the tailwind config palette** (`brand` only declares 50,
100, 500, 600, 700, 900). Tailwind 3 doesn't fail on undefined
custom-palette steps; the class generated is `border-#undefined`
and silently drops. Verify visually — likely the border is invisible
on this gradient card.

🟡 MED: Line 51 — Same: `text-brand-700 ring-brand-200`.
`ring-brand-200` is also missing. The featured card likely has no
visible ring.

🔵 LOW: Line 33 — Description "Nine end-to-end capabilities" matches
FEATURES.length = 9. Good.

🔵 LOW: Line 39 — `ICON_MAP[f.icon] ?? Sparkles` fallback. Good
defensive coding.

---

### 2.21 `website/src/components/landing/Architecture.tsx`

🔵 LOW: Lines 1-3 — Just FEATURE_LAYERS + SectionHeader. Clean.

🔵 LOW: Lines 22-24 — Inline `style={{ background:
linear-gradient(...) }}` uses HEX + 2-digit alpha shorthand (`#4F46E510`).
Modern browsers parse this; older may not. Verify Safari ≥ 15.

🔵 LOW: Lines 36-43 — Items mapped as pills. Good.

🔵 LOW: This component is **duplicated** in `FeatureMap.tsx` lines
39-72 — same layer-card UI. Consider extracting to a shared
`<LayerCard/>`.

---

### 2.22 `website/src/components/landing/Agents.tsx`

🔵 LOW: Lines 6-13 — Hard-coded `AGENT_COLORS` array. Could move to
site-content but six static values, acceptable.

🔵 LOW: Lines 26-46 — Map AGENTS to cards. `a.name.charAt(0)` for
the avatar — works for all 6 names (M, J, S, W, A, P — all distinct).

🟡 MED: Lines 53-62 — `PIPELINE_NODES` rendered as a horizontal flex
wrap. **No semantic role** — it should be `<ol>` (ordered list) so
screen readers can navigate the 13 steps. Currently a `<div>` with
nested chevrons.

🔵 LOW: Line 60 — `text-ink-5` chevron colour is very light; verify
contrast against the surrounding zinc.

---

### 2.23 `website/src/components/landing/ValidationRecon.tsx`

🟠 HIGH: Lines 5-11 — `VALIDATION_BULLETS` has **5 items** but the
section header says **"Eight built-in rules"** (line 26) and the
SplitCard hero is "8 built-in rules" (line 33). Numbers don't add
up. Either:
- Update VALIDATION_BULLETS to include all 8 (matches docs page):
  Row counts, Schema parity, Null bounds, Duplicates, Foreign-key
  referential integrity, Date-range bounds, Domain checks, Business
  rules.
- Or change hero/subtitle to "5 built-in rules" (lying to docs).

🔵 LOW: Lines 13-18 — `RECON_BULLETS` has 4 bullets. Fine for the
recon card.

🔵 LOW: Lines 50-97 — `SplitCard` is a clean local component.

🔵 LOW: Line 86 — `style={{ background: `${accent}1a`, color:
accent }}` — alpha hex 8-digit. Same browser concern as Architecture.

---

### 2.24 `website/src/components/landing/DeveloperWorkspace.tsx`

🔵 LOW: Lines 1-26 — `BULLETS` array, semantic + descriptive. Good.

🔵 LOW: Lines 29-54 — Section composition. Good.

🔵 LOW: Lines 56-93 — `DiffCard` — hand-coded diff with rose / emerald
rows. Visually polished. The minus sign uses `−` (U+2212) — verify
UTF-8 file encoding (it is).

🔵 LOW: Lines 95-109 — `DiffRow` keeps before/after rows aligned.
The wrapping div uses `-mx-3 px-3` to extend background colour to the
parent edges. Clever.

🔵 LOW: Line 98 — The "after" example uses `created_at::TIMESTAMP_NTZ`
— legit Snowflake syntax. Good.

🟡 MED: No `aria-label` on the SQL `<pre>` blocks. Screen readers
will read out every special character.

---

### 2.25 `website/src/components/landing/Roadmap.tsx`

🔵 LOW: Lines 1-13 — Imports + section header. Standard.

🔵 LOW: Lines 14-49 — Maps `ROADMAP` (4 quarters) into 4 cards.
First card (`isNow`) gets the gradient highlight. Good.

🔵 LOW: Line 42 — Non-now items render an empty circle dot. Visual
hierarchy is clear.

🔵 LOW: No semantic timeline-list / no `<ol>` for the quarter order.
For a roadmap, ordered list is the right semantics.

---

### 2.26 `website/src/components/landing/FeatureMap.tsx`

🔵 LOW: Lines 1-12 — Imports + header. Good.

🔵 LOW: Lines 17-37 — Renders `FEATURE_MAP_CHAIN` (9 nodes) as a
chained-chevron flow. Endpoints get the brand pill style.

🟠 HIGH: Lines 39-72 — **The layer card UI is duplicated verbatim
from `Architecture.tsx` lines 13-47**. Two pages now have the same
four-layer cards rendering. On the home page, where both
`<Architecture/>` (line 58) and `<FeatureMap/>` (line 57) are
present, **the user sees the layer cards twice**. Pick one. Likely
remove from FeatureMap and keep the chain only.

🔵 LOW: Lines 21-26 — Endpoint highlighting (`i === 0 || i === len-1`)
is good visual cueing.

---

### 2.27 `website/src/components/landing/DockerInstall.tsx`

🔵 LOW: Lines 1-18 — Same copy handler as `Hero.tsx`. **Duplicated
logic**. Extract a `useCopyToClipboard()` hook.

🔵 LOW: Lines 20-58 — Visually consistent with Hero's install card.

🔵 LOW: Lines 50-56 — "Full installation guide" link points to
`/docs/installation` — exists. Good.

🔵 LOW: Lines 26 — Headline "Get running in under 5 minutes" matches
Hero's "~5 min" pill. Good.

---

### 2.28 `website/src/components/landing/Connectors.tsx`

🟠 HIGH: Line 10 — Subtitle says **"Seven sources out of the box
plus a small Python adapter interface"** — but `CONNECTORS` array
has **8 entries** (7 sources + Custom Connector). Hero pill says
"8 connectors". Reconcile.

🔵 LOW: Lines 12-31 — Grid of connector tiles. Clean.

🟡 MED: Line 19 — `style={{ background: c.color }}` — inline style
is fine but **PostgreSQL's "P", MySQL's "My", and SQL Server's "QS"**
are not standard logo abbreviations. SQL Server's brand mark is "MS
SQL" or "SQL"; "QS" is unusual (Microsoft uses "S" or "MS"). Verify
brand guidelines or use real logos.

🔵 LOW: Lines 25-28 — Truncate behaviour for long names. Good.

---

### 2.29 `website/src/components/landing/CTA.tsx`

🔵 LOW: Lines 7-44 — Gradient CTA panel — well-designed.

🔵 LOW: Line 24 — View demo opens static demo HTML in new tab.
Consistent with Navbar + HERO.

🔵 LOW: Line 32 — GitHub link consistent.

🟡 MED: Lines 13-15 — `grid-faint-bg opacity-20` overlay — using a
class from styles.css. Fine, but `aria-hidden="true"` is already
present which is correct for decorative bg.

🔵 LOW: Line 19-21 — Body copy is short + on-message.

---

### 2.30 `website/src/components/docs/DocsLayout.tsx`

🔵 LOW: Lines 1-7 — Clean props interface.

🔵 LOW: Lines 13-27 — Mobile/small-tablet `<details>` accordion
pattern. Good progressive enhancement.

🔵 LOW: Line 24 — Sidebar is given a different className for mobile
context — appropriate.

🟡 MED: Line 31 — Desktop sidebar has `sticky top-16
max-h-[calc(100vh-4rem)] overflow-y-auto` — but if Navbar height
changes the `top-16` (= 4rem = 64 px) breaks alignment. Navbar's
`h-16` matches (good), but coupling is implicit. Tokenise via a CSS
var like `--header-h`.

🔵 LOW: Line 20 — `cursor-pointer` on a `<summary>` is browser
default; specifying isn't wrong.

---

### 2.31 `website/src/components/docs/DocsSidebar.tsx`

🔵 LOW: Lines 22-35 — `groupFiltered(query)` matches title +
summary. Could expand to section headings + content for richer
search.

🔵 LOW: Lines 53-81 — Renders 9 categories; if a category has zero
matches, hides it. Good UX.

🔵 LOW: Lines 60 — `NavLink to={/docs/${doc.id}}` works because
`/docs/*` route nests into `DocsPage` and matches `:id`.

🟡 MED: Search input has no debouncing. Typing in `useState` rerenders
the entire sidebar on each keystroke. For 21 docs negligible; mention
for the future.

🔵 LOW: Lines 82-86 — Empty-state message is friendly.

🟡 MED: Line 19 — `showActive` prop is declared but **never used in
the render**. The active state is always applied (`if (showActive &&
isActive)` — `showActive` defaults to true and there's no path that
sets it to false). Dead prop API. Remove or use.

🔵 LOW: Line 64 — `end` prop on NavLink ensures exact match. Good.

---

### 2.32 `website/src/components/docs/DocsPage.tsx`

🔵 LOW: Lines 9-19 — `resolveRelatedId(label)`: tries exact match,
falls back to fuzzy. Good defensive design.

🔵 LOW: Lines 21-42 — `Section` renders heading, paragraph,
optional bullets, optional code block. Clean.

🟡 MED: Line 27 — Long content is rendered as a single `<p>`. If
authors add line breaks, they're lost — the strings in
docs-content.ts are single paragraphs by design, but consider
allowing `\n\n` as paragraph separator.

🔵 LOW: Lines 36-39 — Code block uses zinc-900 bg. Good contrast.
No syntax highlighting; a feature gap. Consider Shiki or Prism for
prod.

🔵 LOW: Lines 44-83 — Article frame. Good structure.

🟡 MED: Line 22 — `<section>` for each subsection — accumulates
multiple `<section>` siblings inside `<article>`. Semantically fine
but consider using `<section aria-labelledby="...">` for screen
reader correctness.

🔵 LOW: Line 73 — Non-matching related-feature label falls back to a
styled `<span>` — the className still has `hover:bg-zinc-200` removed
via `.replace(...)`. Brittle string manipulation; cleaner to
conditionally build the className array.

---

### 2.33 `website/src/components/docs/DocsSearch.tsx`

🔵 LOW: Lines 9-25 — Tight, accessible search input with sr-only
label + decorative icon. Good.

🔵 LOW: Line 18 — `type="search"` triggers iOS Safari clear-X
button. Good.

🔵 LOW: No autofocus / no `Cmd-K` / `/` shortcut. Optional.

---

### 2.34 `website/src/components/docs/FeatureDocCard.tsx`

🔵 LOW: Lines 10-42 — Whole-card link. Good UX.

🔵 LOW: Line 38 — `&rarr;` HTML entity. Fine; could use → directly.

🔵 LOW: Lines 22-31 — Related-features pills displayed. Visually
busy on cards with many tags.

🔵 LOW: Line 14 — `focus-ring` applied. Good keyboard a11y.

---

### 2.35 `website/src/pages/HomePage.tsx`

🔵 LOW: Lines 1-15 — Imports the full landing component suite.

🟠 HIGH: Lines 56-62 — Renders both `<FeatureMap/>` and
`<Architecture/>`. **Both render the same 4-layer cards** (see
§2.26). Visitors see the layer-strip twice. Remove from one of them.

🔵 LOW: Lines 17-22 — `SPRINT_TEASER` array — 4 items. Sized for
the sm:2 lg:4 grid. Good.

🔵 LOW: Lines 64-95 — Sprint teaser section. Clean.

🔵 LOW: Lines 72-79 — "Open live console" link → static demo. Good.

🟡 MED: The page renders **11 sections vertically**. On a slow
3G connection this is heavy. Lazy-load below-the-fold sections with
`React.lazy` or, given that this is pure presentational JSX, just
let it ship — the bundle is the issue, not the render cost.

---

### 2.36 `website/src/pages/FeaturesPage.tsx`

🔵 LOW: Lines 1-7 — Imports.

🔵 LOW: Lines 12-25 — Composes Features + FeatureMap +
ValidationRecon + DeveloperWorkspace + Roadmap + CTA.

🟡 MED: Title is "All features" but the page is mostly the same
sections as Home (minus Hero, Architecture, Agents, Connectors,
DockerInstall). Consider differentiating with a feature
matrix / comparison table.

🟡 MED: No per-page `<title>` (see §2.9) so `/features` shows the
home title in the tab. SEO impact.

---

### 2.37 `website/src/pages/ArchitecturePage.tsx`

🔵 LOW: Lines 1-13 — Imports + 6-service SERVICES list.

🔵 LOW: Lines 15-63 — Composes Architecture + Agents + service-table.

🔵 LOW: Lines 66-101 — `<SystemSvg/>` is a hand-crafted SVG flow
diagram. Good a11y with `role="img"` + descriptive `aria-label`.

🟡 MED: Lines 91, 96, 115 — `fontFamily="JetBrains Mono,
ui-monospace, monospace"`. **JetBrains Mono is NOT in the loaded
fonts** — only Space Grotesk + IBM Plex Mono are imported from
Google Fonts. The SVG will fall through to `ui-monospace`. Either:
- Update SVG to `fontFamily="IBM Plex Mono, ui-monospace, monospace"`
  to match the rest of the site.
- Or add JetBrains Mono to the font load.

🟡 MED: Same issue exists in `public/og-image.svg` lines 31, 37, 45.
Open Graph image renders server-side (when crawlers fetch it), so
the rendered look will be the fallback `monospace` glyphs — visually
inconsistent with the rest of the brand.

🔵 LOW: Service `port` for `worker` is "—" (em dash). Consistent
with the no-port reality.

🔵 LOW: Lines 39-58 — Table is responsive — the parent rounds via
`overflow-hidden`. Good, but consider `overflow-x-auto` for very
narrow screens.

---

### 2.38 `website/src/pages/OpenSourcePage.tsx`

🔵 LOW: Lines 1-29 — Imports + 3 inline data arrays.

🟠 HIGH: Lines 23-28 — `RECENT_ACTIVITY` array uses
`when: "Latest"` for every item. **Static fake "Latest" labels** —
visitors see four "Latest" commits dated "Latest" — instantly reads
as a placeholder. Either inject real GitHub data via build-time
fetch, or remove the `when` column, or replace "Latest" with a
real relative date.

🟠 HIGH: Lines 90-92 — `<Badge label="1.2k stars" />` and
`<Badge label="148 forks" />` are **hard-coded marketing numbers**.
If repo stars climb to 5k, the site lies. Either:
- Wire a build-time GitHub API fetch (lots of options:
  `actions/github-script` writes a JSON, Vite imports it).
- Remove badges entirely.
- Add an inline build-time placeholder + clear "(snapshot)" caption.

🔵 LOW: Lines 65-73 — CONTRIBUTING.md CTA opens GitHub in new tab.
Good.

🔵 LOW: Lines 95-110 — File tree shows 7 entries; could match
the real repo. Verify
(`frontend/`, `backend/`, `worker/`, `agents/`, `_bmad/`,
`website/`, `docs/`).

🔵 LOW: Lines 152-159 — `Badge` local component. Clean.

---

### 2.39 `website/src/pages/DocsPage.tsx`

🔵 LOW: Lines 1-7 — Imports — aliases `DocsPage` from the docs
component as `DocReader` to avoid shadowing the page-level
`DocsPage` export. Clean.

🔵 LOW: Lines 9-26 — `DocsIndex` renders all docs as cards. Good.

🔵 LOW: Lines 28-61 — `DocsDetail` handles unknown id with a polite
404. Good.

🟡 MED: The 404 is **client-side only** — Hostinger / Apache returns
200 OK for `/docs/missing-id` because the SPA fallback rewrites it to
`index.html`. Search engines may index it as a soft-404. Add a
`<meta name="robots" content="noindex">` injection or pre-render
known docs and return real 404 for unknown.

🔵 LOW: Lines 32-54 — 404 page also has a "Back to documentation"
CTA. Good.

🔵 LOW: Lines 63-70 — Nested `<Routes>`; works with the outer `/docs/*`
catch.

---

### 2.40 `website/public/robots.txt`

🔵 LOW: 5-line file. `Allow: /` + Sitemap reference. Good.

🟡 MED: No `Crawl-delay`. Google ignores it; some bots respect it.
For a static site bot pressure is irrelevant; skip.

🔵 LOW: Missing `Disallow:` for staging environments, but this is
the prod robots — fine.

---

### 2.41 `website/public/sitemap.xml`

🟠 HIGH: Only **5 URLs** listed:
- `/`
- `/features`
- `/architecture`
- `/docs`
- `/open-source`

The site has **21 doc pages** (`docs-content.ts`). None of the
`/docs/{id}` URLs are in the sitemap. Google will crawl them
eventually via the docs index link, but **explicit sitemap entries
materially improve indexation speed**. Generate sitemap from
docs-content.ts at build time:

```ts
const docUrls = DOCS.map(d => `<url><loc>https://helix.datainteg.io/docs/${d.id}</loc>...</url>`);
```

🔵 LOW: No `<lastmod>` on any URL. Google ignores changefreq +
priority now (since 2020) but still uses lastmod.

🟡 MED: No `<image:image>` blocks (for og-image and feature
screenshots). Image sitemap improves image search.

🔵 LOW: All entries have the same `<changefreq>weekly</changefreq>`.
Google ignores it.

---

### 2.42 `website/public/.htaccess`

🔵 LOW: Lines 4-6 — HTTPS redirect via 301. Good.

🔵 LOW: Lines 9-11 — SPA fallback to `index.html` for non-file /
non-directory requests. Standard.

🟠 HIGH: Lines 14-23 — Security headers block. **Compare with `_headers`:**
the two files **must stay in sync** (one for Apache/Hostinger, one
for Cloudflare/Netlify). Currently they match — good. But there's
**no automated check**. Add a test that diffs the header values
between the two files at build time.

🔵 LOW: Line 15 — HSTS with `includeSubDomains; preload` — solid.
**But the domain is NOT in the Chrome preload list** unless you
submit at <https://hstspreload.org>. Without submission `preload`
is just an aspirational directive.

🔵 LOW: Line 17 — `X-Frame-Options: DENY` is set, and so is `frame-ancestors 'none'`
in CSP. Modern browsers prefer CSP; X-FO is legacy but harmless.

🔵 LOW: Line 18 — `Referrer-Policy: strict-origin-when-cross-origin`
matches the meta tag in index.html. Good.

🔵 LOW: Line 19 — `Permissions-Policy` denies camera, mic,
geolocation, payment, USB. Good. Could also explicitly deny
`interest-cohort` (FLoC), `browsing-topics` (Topics API), `accelerometer`,
`gyroscope`, `magnetometer`, `display-capture`, `screen-wake-lock`,
`fullscreen` (or allow self).

🔵 LOW: Line 20 — `Cross-Origin-Opener-Policy: same-origin` is good.

🟡 MED: Line 21 — `Cross-Origin-Resource-Policy: same-origin` blocks
**third-party embedding** of your assets. If anyone wants to embed
the og-image in their own page (LinkedIn previews work via crawler,
not embed, so fine), it will break. Consider
`Cross-Origin-Resource-Policy: cross-origin` for the og-image.

🟠 HIGH: Line 22 — CSP allows `style-src 'unsafe-inline'`. As called
out in §2.1, this is required by Tailwind's compiled CSS only if you
have inline style attributes (you do: 20+ `style={{ ... }}` in
components). Modern Tailwind generates a static CSS file with no
inline styles for the framework itself — the runtime inline styles
in your components are what require `'unsafe-inline'`. Either:
- Move dynamic colours to CSS custom properties + Tailwind arbitrary
  values that compile to static CSS.
- Accept the trade-off and document it.

🔵 LOW: Lines 25-28 — DEFLATE for common types. Good. Consider
adding `application/wasm`, `font/woff2` (although woff2 is already
compressed).

🔵 LOW: Lines 30-39 — Cache headers. **`text/html` "access plus 1
hour"** is sensible — letting visitors get content updates without
a hard refresh. **JS / CSS "access plus 1 month"** is OK because Vite
hashes filenames so any change cache-busts. ✓

🟡 MED: No `Cache-Control: immutable` directive on hashed assets. Add:

```apache
<FilesMatch "\.(js|css|woff2|svg)$">
  Header set Cache-Control "public, max-age=31536000, immutable"
</FilesMatch>
```

🔵 LOW: No `application/manifest+json` cache rule (no PWA manifest
exists anyway).

🟡 MED: No explicit `Content-Type` overrides — `.htaccess` does not
set `AddType` for `.woff2` or `.svg`. Apache normally infers from
mime.types; verify Hostinger ships it correctly.

---

### 2.43 `website/public/_headers`

🔵 LOW: 9-line global-headers file (Netlify / Cloudflare Pages
format). Matches `.htaccess` value-for-value. Good.

🟡 MED: Same drift risk as `.htaccess`. Single source of truth +
codegen would prevent drift.

🔵 LOW: No path-specific overrides (e.g. cache headers for
`/assets/*`). Cloudflare Pages applies sensible defaults but explicit
beats implicit.

---

### 2.44 `website/public/.well-known/security.txt`

🔵 LOW: Lines 1-5 — Standard RFC 9116 fields.

🟡 MED: `Expires: 2027-05-25T00:00:00.000Z` — 1 year from now (per
the file). RFC 9116 mandates **future expiry** ≤ 1 year. The
expiry date should be re-checked annually; consider an automated CI
warning at T-30 days.

🔵 LOW: Line 4 — `Canonical:` points to itself — RFC-compliant.

🟡 MED: Missing **`Encryption:`** (PGP key URL). Recommended though
optional. Consider hosting a public key.

🟡 MED: Missing **`Acknowledgments:`** — once you have security
researcher hall-of-fame, link it.

🟡 MED: Missing **`PGP-Sign:`** — the file itself should ideally be
PGP-signed in production.

🔵 LOW: No `Hiring:` field — optional but recruiters scrape these.

---

### 2.45 `website/public/favicon.svg`

🔵 LOW: 10-line SVG with brand gradient. Matches BrandMark.tsx
visually. Good.

🟡 MED: Only `.svg` favicon shipped. Older browsers (IE11, some
mobile Safari versions) won't pick it up. Ship `favicon.ico`
(16/32/48) + `apple-touch-icon-180.png` + `android-chrome-192.png`
+ `android-chrome-512.png` and reference them in index.html.

🔵 LOW: Gradient id `helixGradient` — same id as BrandMark. Document
notes elsewhere — fine in isolation.

---

### 2.46 `website/public/og-image.svg`

🟠 HIGH: Lines 1-47 — Open Graph image is **SVG**, which most OG
crawlers (LinkedIn, Slack, Discord, Telegram) **do not render**.
Facebook does not support SVG OG images. Result: most social shares
will display no image. **Rasterise to 1200×630 PNG.**

🟡 MED: Lines 31, 37, 45 — `font-family="JetBrains Mono"` (not
loaded). See §2.37.

🟡 MED: Line 18 — `<text fill="#FFFFFF" letter-spacing="-3">H</text>`
— letter-spacing negative on a single glyph is no-op but flagged
as unusual.

🔵 LOW: Lines 32-44 — Two `<text>` blocks with mock terminal +
checkmark list. Editorial — solid visual.

🔵 LOW: `og:image:width=1200`, `og:image:height=630` is declared in
index.html — matches viewBox. Good.

---

### 2.47 `website/public/helix-console-demo.html` (1.5 MB, line-by-line skipped)

🔴 CRITICAL: **1.5 MB single static file** with embedded base64
manifest + bundler bootstrap. Shipped as a public asset, served on
the same origin as the marketing site. Concerns:

1. **Bundle size**: 1.5 MB on the wire is heavy for a marketing
   demo. The bundle bootstrap (`__bundler_loading` /
   `__bundler_thumbnail` / `__bundler/manifest` script type) is the
   signature of a Figma Make / Anima / Galileo export. The
   "Unpacking..." loader during initial paint is visible to
   visitors. Reasonable for a one-time demo; not OK if it
   blocks LCP on the parent site (it doesn't — it's a separate
   page).

2. **Same-origin asset**: anything inside the demo runs with the
   marketing site's origin. If the bundle contains `eval` (which
   it almost certainly does to unpack the manifest), the CSP
   `script-src 'self'` allows it. Verify the bundler doesn't ship
   `eval`-blocking violations.

3. **Iframe embed**: even though `frame-ancestors 'none'` blocks
   third-party embedding, the demo can iframe itself / make
   `XMLHttpRequest` calls (`connect-src 'self'`). Confirm no calls
   are made.

4. **Privacy / leak risk**: the embedded base64 manifest may include
   **screenshot thumbnails** of the actual console (with real
   project names, demo data). Audit the manifest for any
   `cybersquadmr98@gmail.com` / customer data leakage. (Manifest
   appears to be auto-generated from Figma — likely contains design
   asset URIs, not customer data, but worth confirming.)

5. **Security headers**: the static HTML is served with the
   project's strict CSP. The inline bootstrap script uses
   `'self'` per CSP, so it works. But any `<script
   type="__bundler/...">` block + `eval()` of base64-decoded JS
   means **CSP `script-src 'self'`** alone is not sufficient
   protection. Use a strict CSP that forbids `unsafe-eval` (you
   already do — there's no `'unsafe-eval'` in the policy) and
   verify the demo still loads.

🟠 HIGH: **Replace with a static screenshot for production**:
1.5 MB is a lot of bandwidth for a marketing demo when one good
PNG could do the job. Keep the interactive HTML for an
opt-in "explore live console" CTA.

🟡 MED: The "Unpacking..." loader is brand-inconsistent — it uses
Apple-system-font and a placeholder spinner. Theme it to match Helix.

🟡 MED: No HTML `<title>` other than "Helix Console — Migration
Command Center". No meta description. If this URL gets shared, it
has no preview.

🟡 MED: No `<meta name="robots" content="noindex">` on the demo
HTML — Google will index it. The demo content (mock data,
"Unpacking..." UI) is probably not what you want in search results.
**Add `noindex`** at minimum.

---

## 3. Cross-cutting findings

### 3.1 SEO completeness

| Area | Status | Notes |
|---|---|---|
| `<title>` per route | FAIL | Only the home title ships — every route shows the same `<title>`. Add Helmet/route-level title injection. |
| Canonical | OK | `index.html` declares canonical to root. But sub-routes will inherit the same canonical → Google sees all routes as duplicates of `/`. Add per-route canonical. |
| Meta description per route | FAIL | Same issue as title. |
| Open Graph image | FAIL | SVG used. Most crawlers won't render. Rasterise. |
| Twitter card | OK (partial) | `summary_large_image` set but `twitter:site` / `twitter:creator` missing. |
| JSON-LD | PASS | Valid `SoftwareApplication` schema; missing `softwareVersion`, `datePublished`, `aggregateRating`. |
| `sitemap.xml` | FAIL | Missing all 21 `/docs/{id}` URLs. |
| `robots.txt` | OK | `Allow: /` + sitemap ref. Good. |
| 404 handling | FAIL | Server returns 200 for any URL because of SPA fallback + catch-all redirect to `/`. Soft-404 risk. |
| Lighthouse SEO score | (run it) | Likely 85-92 because of title/description inheritance. |
| Image alt text | N/A | No raster images. |
| URL slug quality | OK | `/docs/code-review-center`, `/docs/agent-workflow` — clean. |
| Hreflang | N/A | English only. |
| `prerender` for crawlers | OPTIONAL | Vite SPA is JS-rendered. Modern Googlebot renders JS but Bing + small bots may not. Consider `vite-plugin-prerender-spa` or moving the marketing tree to Astro for SSR. |
| Performance impact on SEO | MED | LCP likely 1.5-2.5 s due to font loading. Preload + subset would shave 300 ms. |

### 3.2 Security headers

| Header | Apache | _headers | Risk |
|---|---|---|---|
| HSTS | OK | OK | Not in preload list — submit via hstspreload.org or remove `; preload` directive. |
| CSP | OK | OK | `unsafe-inline` in `style-src` weakens to ~70% of strict. No `script-src-elem`. No `report-uri`. No nonces. |
| X-Content-Type-Options | OK | OK | `nosniff` — good. |
| X-Frame-Options | OK | OK | `DENY`. |
| Referrer-Policy | OK | OK | `strict-origin-when-cross-origin`. |
| Permissions-Policy | OK | OK | Five sensors denied. Could expand. |
| COOP | OK | OK | `same-origin`. |
| CORP | OK | OK | `same-origin` — may break public asset embedding. |
| COEP | MISSING | MISSING | `Cross-Origin-Embedder-Policy` not set. Required for `SharedArrayBuffer` / cross-origin isolation, but not needed for marketing site. Skip. |
| HPKP | N/A | N/A | Deprecated. Don't add. |
| Expect-CT | N/A | N/A | Deprecated. Don't add. |
| X-XSS-Protection | MISSING | MISSING | Deprecated; CSP supersedes. OK to skip. |

Concrete diff between `.htaccess` and `_headers` — **none** (audited
manually); they're verbatim copies. Future drift is the risk.

`rel="noopener noreferrer"` audit:
- 12 `target="_blank"` links across the site.
- All use `rel="noreferrer"` only — no explicit `noopener`.
- Per HTML living standard, `noreferrer` implies `noopener` in
  modern browsers — but for IE11 / legacy webviews / cautious
  CSP audits, **add `noopener` explicitly**. Find-replace
  `rel="noreferrer"` with `rel="noopener noreferrer"`.

### 3.3 Accessibility

| Concern | Status | Where |
|---|---|---|
| Skip-to-content link | MISSING | `WebsiteLayout.tsx` — no skip link, no `id="main"`, no `tabIndex={-1}`. |
| Heading hierarchy | OK | Single `<h1>` per page (Hero / SectionHeader), `<h2>` per section. Docs have `<h1>` (title) + `<h2>` per subsection. |
| Focus rings | PARTIAL | `.focus-ring` class exists and is used on most CTAs / inputs. Some nav links (NavLink desktop) inherit default browser ring. Audit all interactive elements. |
| Color contrast | MOSTLY OK | `ink-3` (#52525B) on `surface` (white) = ~7.0:1. `ink-4` (#71717A) on white = ~4.7:1 (passes AA for normal text but fails AAA). `text-ink-5` (#A1A1AA) on white = 2.9:1 → fails AA except for large text. Audit usages — used in chevron icons, footer fine print. |
| Reduced motion | MISSING | `.section-fade-in` animates regardless of `prefers-reduced-motion`. |
| Keyboard nav | MOSTLY OK | All links/buttons are real `<a>`/`<button>`. Mobile menu has no Esc handler. |
| Screen reader labels | MOSTLY OK | BrandMark, mobile-menu button, copy button, SVG diagram all have labels. Diff `<pre>` blocks have no ARIA. |
| `aria-expanded` on menu toggle | MISSING | Navbar mobile button does not bind `aria-expanded={open}`. |
| `<ol>` for numbered sequences | MISSING | Pipeline (Agents), Roadmap, Feature map — all rendered as `<div>` flex. Should be `<ol>` for semantic structure. |
| Form labels | OK | DocsSearch has `<label className="sr-only">`. |
| Live regions | MISSING | Copy button "Copied" feedback has no `aria-live` — screen readers won't hear the success. Add `aria-live="polite"` to the button or to a separate span. |
| Forced-colours-mode | UNTESTED | `.gradient-text` will go invisible in Windows High Contrast. Provide fallback. |

### 3.4 Mobile responsiveness

| Page / section | Mobile state |
|---|---|
| Navbar | Hamburger toggle works; menu is full-width drawer. Good. No body scroll lock. |
| Hero | Stacks correctly. Install card uses `whitespace-pre-wrap break-all` on small + `whitespace-pre` on `md+`. Good. |
| Features grid | `grid-cols-1 md:grid-cols-2 lg:grid-cols-3` — good. |
| Architecture layer cards | `flex-col md:flex-row` — good. |
| Agents grid | `grid-cols-2 md:grid-cols-3` — good. |
| Pipeline chain | Wraps with `flex-wrap`. The 13 pills + chevrons wrap awkwardly on mobile (chevron orphaned at line break). Consider hiding chevrons below `md`. |
| Connectors grid | `grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6` — good. |
| Validation/Recon | `grid-cols-1 md:grid-cols-2` — good. |
| DeveloperWorkspace DiffCard | Two-column diff side-by-side regardless of viewport (`grid-cols-2`). On mobile each column is 50%, content overflows. Stack to `grid-cols-1 md:grid-cols-2`. |
| DockerInstall | Stacks. Good. |
| Roadmap | `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4` — good. |
| CTA panel | Stacks. Good. |
| Docs sidebar | Mobile uses `<details>` accordion — good progressive enhancement. |
| Docs index cards | `sm:grid-cols-2` — good. |
| Architecture SVG | `w-full h-auto` — scales. But 820×220 viewBox + 5 boxes is **cramped on phones**. Below ~500 px the labels overlap. |
| Open Source page | `grid-cols-1 md:grid-cols-2` — good. |

### 3.5 Bundle size + chunking

```
dist/assets/index-DwLCViTC.js   ≈ 255 KB (uncompressed; ~80-90 KB gzip estimated)
dist/assets/index-Cl3wD1Mk.css  ≈  25 KB (~5-7 KB gzip estimated)
dist/helix-console-demo.html    ≈ 1.5 MB (separately loaded; not in critical path)
```

- **No code splitting**: every page in one chunk. Recommended:
  `vendor` (react/react-dom/react-router-dom) + `app` + lazy `docs`.
  Could shave 50-80 KB off initial bundle by lazy-loading docs.
- **Lucide tree-shaking**: ~24 icons imported across the site. Each
  Lucide icon is ~1.5 KB. The 255 KB includes the React runtime
  (~45 KB), React-DOM (~120 KB), React Router (~25 KB), Lucide icons
  (~35 KB), app code (~30 KB). Reasonable.
- **Font payload**: Space Grotesk + IBM Plex Mono (4 weights each)
  = ~120-180 KB woff2. Not in JS bundle but separate request.
  Subset to Latin and only required weights — save ~60-90 KB.
- **CSS**: 25 KB is fine. Tailwind purge is working.
- **No `vite-bundle-visualizer`** plugin. Add for ongoing audit.

### 3.6 Content consistency

🟠 HIGH: **Connector count drift**:
- Hero pill: "8 connectors" (`Hero.tsx:71`)
- Connectors subtitle: "Seven sources out of the box plus a small
  Python adapter interface" (`Connectors.tsx:10`)
- `CONNECTORS` array: 7 sources + 1 Custom = 8 entries
- `site-content.ts:114` comment: "8 shipped connectors + extension
  point" — wording suggests 8 *separate from* the extension point
  (off by one).
- `docs/connector-framework` says: "PostgreSQL · MySQL · SQL Server
  · Snowflake · S3 · CSV · Excel · custom" — 7 + custom = matches
  the array.

**Recommended fix**: pick "**7 connectors + a custom adapter**" as
the canonical phrasing. Update Hero pill to "7 connectors", update
`Connectors.tsx` subtitle to "Seven sources out of the box plus a
custom adapter interface", and add a comment in `site-content.ts`
to source the truth.

🟠 HIGH: **Validation rule count drift**:
- ValidationRecon section header: "Eight built-in rules"
- SplitCard hero: "8 built-in rules"
- `VALIDATION_BULLETS` array: **5 items** (Row counts, Null checks,
  Duplicates, Schema parity, Business rules)
- `docs/validation-guide` lists **8 rules**: Row count parity,
  schema parity, null bounds, duplicates, foreign-key referential
  integrity, date-range bounds, domain checks, custom business rules.

**Recommended fix**: expand `VALIDATION_BULLETS` to all 8 rules,
matching the docs source of truth. Or change the hero to "5 core
checks + more".

🟡 MED: **First-pipeline-node drift**:
- `PIPELINE_NODES[0]` (site-content.ts): `"Requirement Intake"`
- `docs/agent-workflow.sections[1].bulletPoints[0]`: `"Winston ·
  project context"`

Same step, different name. Pick one.

🟡 MED: **LLM provider model list aspirational**:
- `docs/llm-provider-setup` lists `gpt-5.5`, `claude-opus-4-7`,
  `gemini-3-pro/flash`. These models do not yet exist in public
  general availability. Update before launch or document as a
  forward-looking list.

🟡 MED: **GitHub stat numbers fabricated**:
- `OpenSourcePage.tsx:90-91`: "1.2k stars · 148 forks" hard-coded.
  Risk of mismatch with reality.

🟡 MED: **Recent activity placeholders**:
- `RECENT_ACTIVITY` all `when: "Latest"` — clearly placeholder
  copy. Replace with real timestamps.

🟡 MED: **README outdated**:
- README mentions `/demo` route, `demo-data.ts`, `components/demo/`,
  `pages/DemoPage.tsx` — all removed.

🟡 MED: **Footer / nav cross-reference**:
- Footer "System Design" links to `/docs/architecture` — exists.
- Footer "Security" links to `/docs/security-model` — exists.
- Footer "Connector Guide" links to `/docs/custom-connector-guide`
  — exists.
All link targets exist. Good.

🔵 LOW: **Tagline duplication**:
- `SITE.tagline = "Open-source AI-powered migration and validation platform."`
- Used in Hero eyebrow, Footer, OpenSourcePage header, DockerInstall
  eyebrow. Consistent ✓.

🔵 LOW: **Number-style inconsistency**:
- Sometimes "13-step" (Hero pill), sometimes "13-node" (FEATURES),
  sometimes "13 steps" (Agents). Pick one.

---

## 4. Severity summary

| Severity | Count |
|---|---|
| CRITICAL | 1 |
| HIGH     | 13 |
| MED      | 33 |
| LOW      | 62 |

Roll-up of the named CRITICAL / HIGH items:

- 🔴 CRITICAL — `helix-console-demo.html` is 1.5 MB. Recommend
  replacing with a screenshot for production.
- 🟠 HIGH — CSP `style-src 'unsafe-inline'` (justified but
  document).
- 🟠 HIGH — No font preload → 150-300 ms LCP penalty.
- 🟠 HIGH — `lucide-react` version range — tree-shake verification.
- 🟠 HIGH — `<main>` has no `id` and no skip-link.
- 🟠 HIGH — Hero "View GitHub" awkward wording.
- 🟠 HIGH — Mobile menu has no body-scroll lock.
- 🟠 HIGH — `tailwind.config.ts` `brand-200` missing → invisible
  borders in 5+ places.
- 🟠 HIGH — `agent-workflow` doc lists aspirational model names
  (`gpt-5.5`).
- 🟠 HIGH — `VALIDATION_BULLETS` says "Eight built-in rules" but
  lists 5.
- 🟠 HIGH — Layer cards rendered twice on home page.
- 🟠 HIGH — "Seven sources" vs "8 connectors" inconsistency.
- 🟠 HIGH — `og-image.svg` is SVG (most OG crawlers won't render).
- 🟠 HIGH — `sitemap.xml` missing all 21 `/docs/*` URLs.
- 🟠 HIGH — `OpenSourcePage` has fabricated `1.2k stars` /
  `148 forks` and `"Latest"` placeholders.
- 🟠 HIGH — `helix-console-demo.html` lacks `noindex` meta.

---

## 5. Top 10 prioritized fixes

| # | Issue | File:line | Severity | Effort |
|---|---|---|---|---|
| 1 | Replace 1.5 MB Figma-bundler demo HTML with rasterised screenshot (PNG ~150 KB) + keep interactive demo behind opt-in CTA. Add `<meta name="robots" content="noindex">` to demo HTML in the meantime. | `website/public/helix-console-demo.html` | CRITICAL | 1 d |
| 2 | Rasterise `og-image.svg` to `og-image.png` (1200×630) and update OG/Twitter meta tags. Most social crawlers reject SVG. | `index.html:23, 27`; `website/public/og-image.svg` | HIGH | 2 h |
| 3 | Expand `sitemap.xml` to include all 21 `/docs/{id}` URLs (preferably generate from `docs-content.ts` at build time). | `website/public/sitemap.xml`; new build script | HIGH | 3 h |
| 4 | Resolve connector-count drift: pick "7 connectors + custom adapter" everywhere. | `Hero.tsx:71`; `Connectors.tsx:10`; `site-content.ts:114,118-127` | HIGH | 30 min |
| 5 | Resolve validation-rule-count drift: expand `VALIDATION_BULLETS` to 8 entries matching `docs/validation-guide`. | `ValidationRecon.tsx:5-11` | HIGH | 15 min |
| 6 | Add per-route `<title>` + `<meta description>` + canonical via `react-helmet-async`. | `main.tsx`; each `pages/*` | HIGH | 4 h |
| 7 | Add **skip-to-content link** + `id="main"` to `<main>` + `tabIndex={-1}`. | `WebsiteLayout.tsx:9` | HIGH | 30 min |
| 8 | Remove duplicate layer-card rendering on Home (either from `FeatureMap` or `Architecture`). | `HomePage.tsx:57-58`; `FeatureMap.tsx:39-72` | HIGH | 30 min |
| 9 | Replace fabricated GitHub badges (`1.2k stars`, `148 forks`) + `"Latest"` placeholders with build-time GitHub API fetch or remove entirely. | `OpenSourcePage.tsx:23-28, 90-91` | HIGH | 4 h (with API) / 15 min (remove) |
| 10 | Add `brand-200`, `brand-300`, `brand-400`, `brand-800` to `tailwind.config.ts` so existing usages render correctly. | `tailwind.config.ts:24-31` | HIGH | 10 min |

Honorable-mention runners-up (would be 11-20):

11. Add font preload (`<link rel="preload" as="font">`) for the two
    woff2 files used in the LCP.
12. Update `agent-workflow` LLM model list (no `gpt-5.5`, etc.).
13. Add `aria-expanded` to mobile menu toggle.
14. Add `prefers-reduced-motion` override for `section-fade-in`.
15. Replace `target="_blank" rel="noreferrer"` with `rel="noopener
    noreferrer"` everywhere (12 occurrences).
16. Update README — remove `/demo` route + `demo-data.ts` references.
17. Add lazy-loading + chunk splitting (`vendor` vs `app`).
18. Pre-render docs as static HTML (vite-plugin-prerender-spa) for
    better SEO indexation.
19. Add ErrorBoundary at the root.
20. Replace `<span>` chain in Pipeline / Roadmap / FeatureMap with
    semantic `<ol>` for screen readers.

---

## 6. Architecture suggestions

### 6.1 Should docs ship as MDX instead of in-file TS?

**Current**: `docs-content.ts` is a 300-line typed array; authors
edit TypeScript to change a paragraph.

**Pros of current**:
- Type-safe: TypeScript flags missing fields at build time.
- One file = one PR diff = easy review.
- Code editor autocompletes section structure.

**Cons of current**:
- Multi-paragraph prose lives in a single string with no formatting.
- Code blocks need manual escaping.
- Markdown features (tables, link references, footnotes) unavailable.
- 300 lines today, 1000 lines at 50 docs.

**Recommendation**: Migrate to **MDX with `@mdx-js/rollup` +
`vite-plugin-mdx`**. Keep the metadata (id, category, summary,
relatedFeatures) as MDX frontmatter; the prose becomes real
markdown. Each doc gets its own file in `src/docs/{id}.mdx`. The
`DOC_CATEGORIES` + `findDoc` helpers move to a glob-import at build
time. Better authoring experience, same type safety on metadata.

### 6.2 Should the static-HTML demo be replaced by a screenshot?

**Yes — at the marketing layer.** 1.5 MB for a demo that visitors
look at for 10 seconds is bandwidth-wasteful and hurts perceived
performance on mobile. Two-tier approach:

1. **Default**: `og-image.png` + a 300-500 KB curated screenshot
   PNG/WebP set rendered inline on the marketing page as a
   "screenshot tour". Lazy-loaded, native `<img loading="lazy">`.
2. **Opt-in**: a "Open live demo" CTA opens the 1.5 MB HTML in a
   new tab for the small % of visitors who want to interact.

This is also better for SEO (Google indexes images; lazy-loaded
HTML is hidden until clicked).

### 6.3 Is the static-HTML demo a privacy / leak risk?

**Risk: low-medium**, contingent on the manifest contents.

- The bundler bootstrap uses `eval`/`Function` to unpack the
  base64 manifest. CSP `script-src 'self'` allows this **only if
  `'unsafe-eval'` is also present**. CSP **doesn't** allow
  `'unsafe-eval'` — therefore the bundle may currently be **broken
  on real visitors with strict CSP enforced**. Verify the demo
  actually renders in production by opening
  `https://helix.datainteg.io/helix-console-demo.html` with browser
  devtools open (look for CSP violations).
- If it does render, the bundle is either avoiding eval (using
  `new Function()`, which is also blocked by CSP, OR fetching JSON
  via `connect-src`, which is also restricted) or the CSP is being
  overridden at the demo HTML level (it has its own inline `<meta
  http-equiv="Content-Security-Policy">`? — read more of the file
  to confirm).
- **Manifest contents**: base64 manifest is opaque to the reviewer
  without decoding. Audit it for:
  - real customer org names / project names
  - real API endpoints (any `helix.datainteg.io/api/*` URLs)
  - real credential / secret strings
  - real user emails (`cybersquadmr98@gmail.com`?)

If the manifest is purely Figma-generated UI assets (most likely),
risk is just bandwidth. If it contains snapshots of real console
data (possible if it was built from a screen-record), that's a
**privacy leak**. Recommend running `grep -aoE
"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}"
helix-console-demo.html` to scan for email addresses.

### 6.4 Other architectural suggestions

- **Consider Astro for the marketing tree.** It would give per-page
  static HTML, native MDX support, image optimisation pipeline,
  built-in sitemap generation, and partial hydration ("islands") so
  only the components that need interactivity (copy button, mobile
  menu, docs search) ship JS. Likely 100-150 KB JS reduction.
- **Build-time GitHub data fetch.** GitHub API → JSON file imported
  at build time. Eliminates fabricated star counts.
- **Single source of truth for headers.** Generate `.htaccess` +
  `_headers` from one YAML/TS file at build time.
- **Tokenise the design system.** `--header-h`, `--brand-50` ...
  `--brand-900` as CSS custom properties so Tailwind classes
  ≅ CSS vars ≅ inline styles share one palette. Currently the
  inline-style hex values (`#4F46E5`, `#06B6D4`) in 8+ components
  duplicate the Tailwind palette.
- **Image pipeline.** Once raster images exist, integrate
  `vite-plugin-imagemin` + responsive `<picture>` blocks.
- **Add Playwright smoke test.** Visit /, /docs, /docs/installation,
  /open-source, /architecture, /features — assert no JS errors, no
  CSP violations, correct `<title>`, correct status codes. Catches
  config regressions.
- **Move docs prose to translation-ready format.** When you do go
  multi-language (i18next or Format.js), MDX with frontmatter
  locales is the cleanest path.
- **Add a `/changelog` route.** "What's new in 0.x" — a perennial
  marketing win, easy with MDX.
- **Strip `unsafe-inline` from CSP `style-src`.** Refactor inline
  `style={{...}}` to Tailwind arbitrary values or CSS variables,
  then drop `'unsafe-inline'`. Material security improvement.
- **Hash-pinned font imports.** Self-host the two woff2 files in
  `public/fonts/` with `Cache-Control: immutable` instead of relying
  on Google Fonts (which adds a third-party DNS + cert handshake +
  cookie surface).

---

*End of review.*
