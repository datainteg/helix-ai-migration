# Helix Migration — Public Website

Marketing landing + interactive demo + A-to-Z documentation. Lives in
`website/` and is **deployed separately** from the authenticated frontend
app in `frontend/`. Visitors should never have to install the backend to
understand the product.

> **Target:** `helix.datainteg.io`
> **Repo:** [datainteg/helix-ai-migration](https://github.com/datainteg/helix-ai-migration)
> **License:** Apache 2.0

## Tech stack

- Vite + React 18 + TypeScript
- Tailwind CSS 3
- React Router v6
- lucide-react icons

No backend dependency. Builds to a static bundle in `dist/` suitable for
any CDN (Cloudflare Pages, Vercel static, Netlify, S3 + CloudFront).

## Quick start

```bash
cd website
npm install
npm run dev      # http://localhost:5173
npm run build    # → dist/
npm run preview  # serve dist/ on :5174
```

## Folder structure

```
website/
├── package.json
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── README.md
└── src/
    ├── main.tsx           # entry — wraps App in BrowserRouter
    ├── App.tsx            # routes
    ├── styles.css         # tailwind + utility classes
    ├── data/
    │   ├── site-content.ts   # marketing copy + nav + features + roadmap
    │   ├── demo-data.ts      # all /demo mock data (projects, agents, ...)
    │   └── docs-content.ts   # every docs page — content-driven
    ├── components/
    │   ├── layout/    # Navbar, Footer, WebsiteLayout, SectionHeader
    │   ├── landing/   # Hero, Features, Architecture, Agents, ...
    │   ├── demo/      # 10 demo components + DemoShell + DemoSidebar
    │   └── docs/      # DocsLayout, DocsSidebar, DocsPage, FeatureDocCard
    └── pages/
        ├── HomePage.tsx
        ├── FeaturesPage.tsx
        ├── ArchitecturePage.tsx
        ├── DemoPage.tsx
        ├── DocsPage.tsx
        └── OpenSourcePage.tsx
```

## Updating content

| To change | Edit |
|---|---|
| Hero copy / nav / footer | `src/data/site-content.ts` |
| Demo numbers / agents / projects | `src/data/demo-data.ts` |
| Documentation pages | `src/data/docs-content.ts` |
| Theme tokens (colors, radii) | `tailwind.config.ts` |

Adding a new docs page = appending an entry to the `DOCS` array in
`docs-content.ts`. No new component files required.

## Separation from `frontend/`

This site is the **public marketing + docs surface**. The authenticated
product (login, dashboards, project management, sprints) lives in
[`../frontend/`](../frontend) and is a Next.js app. Do not add product
pages here — keep this site fast, static, and visitor-friendly.

## Content rules

- AI-generated code + notebook drafts always require **human review** before
  they ship.
- Helix stores **metadata + recon summaries** — never source/target row-level
  data.
- No managed dependency, no telemetry phone-home.
- Apache 2.0 + self-hosted by design.
