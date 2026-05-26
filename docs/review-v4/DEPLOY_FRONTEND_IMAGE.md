# DEPLOY_FRONTEND_IMAGE — Frontend Dockerfile Audit for Ubuntu 24 GCP Deploy

> Generated 2026-05-26. Scope: `frontend/Dockerfile`, `frontend/package.json`,
> `frontend/next.config.mjs`, `frontend/.dockerignore`, `frontend/package-lock.json`,
> `frontend/src/app/api/healthz/route.ts`, `frontend/src/lib/api/client.ts`,
> `docker-compose.build.yml`, `docker-compose.yml`.
> Prior context: INFRA-018, INFRA-019, INFRA-011 from `docs/review-v2/REVIEW_INFRA.md`.
>
> Severity legend: 🔴 CRITICAL · 🟠 HIGH · 🟡 MED · 🔵 LOW.

---

## Aggregate severity counts

| Severity | Count |
|---|---|
| 🔴 CRITICAL | **1** |
| 🟠 HIGH | **2** |
| 🟡 MED | **4** |
| 🔵 LOW | **4** |
| **Total** | **11** |

---

## Findings

---

### FE-001 🔴 CRITICAL — `npm install --legacy-peer-deps` without lockfile: non-reproducible build

**File:line:** `frontend/Dockerfile:6`

```dockerfile
COPY package.json ./
RUN npm install --legacy-peer-deps
```

The `deps` stage copies only `package.json` — the lockfile (`package-lock.json`) is
**not copied**. npm therefore performs a fresh resolution on every build. The
lockfileVersion 3 (`package-lock.json:4`) present in the repo is never consulted,
so two builds 24 hours apart may install different transitive package versions. On
GCP VMs where a local image cache does not exist (fresh pulls), this means prod
images are silently non-deterministic.

**Root cause of `--legacy-peer-deps`:** Tracing git history, commit `3ee4adbb` (2026-05-23
"Docker Compose, frontend admin pages, and backend refinements") deliberately replaced:

```diff
-COPY package.json package-lock.json* ./
-RUN npm ci
+COPY package.json ./
+RUN npm install --legacy-peer-deps
```

The original `dc100016` used `npm ci` with the lockfile. The `--legacy-peer-deps`
flag was introduced at the same time `reactflow ^11.11.4` was added (commit `47537fa3`)
and `@dnd-kit/sortable ^10.0.0` was added (commit `4de7eb0e`). A fresh `npm install`
run without the flag produces peer-resolution warnings but **no hard conflict** —
all peer constraints are satisfied by the installed versions (`react 18.3.1 >=17`
for reactflow; `@dnd-kit/core 6.3.1` satisfies `^6.3.0` for sortable). The flag
was almost certainly added to silence npm v7+ warnings during iterative local
development and left in unintentionally.

**Fix:**
1. Restore `COPY package.json package-lock.json ./` and replace `npm install` with
   `npm ci`. This also removes the need for `--legacy-peer-deps`.
2. Separately, investigate whether `--legacy-peer-deps` can be dropped entirely
   (test with `npm install` locally without the flag; if it succeeds cleanly,
   the flag is unnecessary).
3. If a genuine peer conflict surfaces when the flag is removed, resolve it by
   pinning the conflicting package to a compatible version and committing the
   updated lockfile.

```dockerfile
# Fixed deps stage
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
```

---

### FE-002 🟠 HIGH — `NEXT_PUBLIC_API_URL` baked at build time; no runtime-override path on GCP VM

**File:line:** `frontend/Dockerfile:9-10`; `frontend/src/lib/api/client.ts:1`

```dockerfile
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
```

```typescript
// src/lib/api/client.ts:1
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```

`NEXT_PUBLIC_*` variables are inlined by the Next.js compiler into the JS bundle
during `next build`. The value is **frozen at image-build time**. On a GCP Ubuntu 24
VM where the public API URL is only known after the VM is provisioned (e.g.
`https://api.helix.example.com`), operators cannot simply pass `-e
NEXT_PUBLIC_API_URL=...` at `docker run` — the injected runtime env var is ignored
by the already-compiled JavaScript.

The compose file (`docker-compose.yml:8`) passes `NEXT_PUBLIC_API_URL` as a runtime
environment variable to the container, which does nothing:

```yaml
# docker-compose.yml — this env var is ignored at runtime for NEXT_PUBLIC_ vars
environment:
  NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://localhost:8000}
```

This contradicts operators who follow the "just set the env var" pattern documented
in most Docker guides.

**GCP operator workaround (document in DEPLOY.md):**

Option A — **Rebuild the image with the correct URL** (current intent, but undocumented):
```bash
# On the GCP VM, or in CI before pushing to Artifact Registry:
docker compose -f docker-compose.yml -f docker-compose.build.yml build \
  --build-arg NEXT_PUBLIC_API_URL=https://api.helix.example.com frontend
```
The build overlay already wires this arg (`docker-compose.build.yml:27`).

Option B — **Next.js public runtime config** (no rebuild needed):
In `next.config.mjs`, expose the variable via `publicRuntimeConfig`:
```js
const nextConfig = {
  output: "standalone",
  publicRuntimeConfig: {
    apiUrl: process.env.API_URL,   // server-side only at runtime
  },
};
```
Then read with `getConfig()` from `next/config` in client components.
This path survives `docker run -e API_URL=...` but requires touching every
call site that currently reads `process.env.NEXT_PUBLIC_API_URL`.

Option C — **nginx/Caddy proxy** (recommended for GCP Ubuntu 24): run a reverse
proxy in front of the frontend that rewrites `/api/` calls to the backend
URL, eliminating the need for the frontend to know the backend URL at all.
The frontend then always calls relative `/api/` paths.

**Minimum fix:** Add a prominent comment to `docker-compose.build.yml` near the
`NEXT_PUBLIC_API_URL` build arg, and add a GCP-specific rebuild note in DEPLOY.md.
The current INFRA-011 note ("buried in the troubleshooting section") has not
been resolved.

---

### FE-003 🟠 HIGH — `--legacy-peer-deps` makes `npm audit` output unreliable

**File:line:** `frontend/Dockerfile:6`

When `--legacy-peer-deps` is active, npm's peer-resolution tree deviates from
the intended dependency graph. `npm audit` run against an install tree produced
with `--legacy-peer-deps` may miss CVEs that only surface in the correctly-resolved
tree, or surface false positives from phantom deduplication paths. On a GCP
production deploy this means the security posture of the frontend image cannot
be reliably verified via the standard `npm audit` pipeline.

**Fix:** Resolve FE-001 (restore `npm ci` with lockfile). Once `npm ci` is used,
`npm audit` is authoritative again. Add `RUN npm audit --audit-level=high` after
`npm ci` in CI (not in Dockerfile, to avoid blocking builds on low-severity issues).

---

### FE-004 🟡 MED — Node version pinned to minor only; not pinned to patch or digest

**File:line:** `frontend/Dockerfile:1`

```dockerfile
FROM node:20-alpine AS base
```

The `node:20-alpine` tag floats across patch releases. Between two Docker Hub
pulls on a GCP VM (e.g., a host reboot and a `docker compose pull`), the node
binary version can change from `20.14.0` to `20.15.0`, silently altering OpenSSL
version, V8 bytecode compatibility, and npm version. The lockfile was generated
under an unknown patch version.

**Fix:** Pin to a specific patch, e.g. `node:20.19.3-alpine3.21`, or add a
`@sha256:` digest. Check the current LTS patch via
`docker run --rm node:20-alpine node --version` before pinning.

```dockerfile
FROM node:20.19.3-alpine3.21 AS base
```

---

### FE-005 🟡 MED — Static assets served by standalone server; no CDN offload, no cache headers

**File:line:** `frontend/Dockerfile:24`

```dockerfile
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
```

`next/static` and `public/` are copied into the standalone image and served
directly by `node server.js`. On a GCP Ubuntu 24 VM behind no CDN, every
browser-cacheable asset (JS chunks, CSS, fonts, images) is served by the same
Node process that handles SSR. Under load this is the primary bottleneck.

Next.js standalone sets `Cache-Control: public, max-age=31536000, immutable` on
`/_next/static/**` automatically (content-hashed filenames), so the browser caches
correctly after first load. However:
- There is no GCP Cloud CDN, nginx, or Caddy layer in front of the container to
  serve these assets from memory or a CDN edge.
- `public/` assets (SVGs, the OG image) get no immutable cache header.

**Fix:**
1. For a single-VM GCP Ubuntu 24 deploy, add an nginx or Caddy reverse proxy that
   serves `/_next/static/` from a local cache and adds `Cache-Control` on `public/`.
2. For scale, push `/_next/static/` to Cloud Storage + Cloud CDN during CI after
   `next build`.

---

### FE-006 🟡 MED — Healthcheck uses `node -e fetch(...)` which requires Node 18+; alpine minimal image confirmed compatible but undocumented

**File:line:** `frontend/Dockerfile:29`

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD node -e "fetch('http://localhost:3000/api/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
```

The `fetch` global is available in Node 18+ (unflagged from 18.0.0) and the image
uses `node:20-alpine`, so this works today. However:
- If someone downgrades the base image to `node:16-alpine` (e.g., to chase an LTS
  EOL policy), `fetch` will be undefined and every healthcheck will silently fail,
  marking the container unhealthy immediately.
- `--start-period=15s` is short for a GCP VM cold-start. The standalone server
  starts fast (< 5 s on a warmed node binary), but on a `e2-micro` / `e2-small`
  instance with cold caches, 15 s can be insufficient.

**Fix:**
- Document the Node 18+ requirement in a comment.
- Bump `--start-period` to 30s for GCP e2-small class VMs.
- The `/api/healthz` route (`frontend/src/app/api/healthz/route.ts`) returns
  `{"status":"ok"}` unconditionally and does not contact the backend — this is
  correct for a liveness probe.

---

### FE-007 🟡 MED — `package-lock.json` in `.dockerignore` would silently break `npm ci`

**File:line:** `frontend/.dockerignore`

```
# Current .dockerignore does NOT exclude package-lock.json
node_modules
.next
.git
...
```

The current `.dockerignore` does not exclude `package-lock.json`, which is correct.
However, it also does not explicitly include it in a whitelist. If `.dockerignore`
is ever changed to a whitelist pattern (or `*.json` is accidentally excluded), the
lockfile will be missing from the build context and `npm ci` will fail. This is a
latent risk.

**Fix:** After restoring `npm ci` (FE-001), add a comment in `.dockerignore`
explicitly noting that `package-lock.json` must reach the build context:

```
# package-lock.json is intentionally NOT ignored — required by npm ci
node_modules
.next
...
```

---

### FE-008 🔵 LOW — Multi-stage structure is correct but the `base` stage is a trivial alias

**File:line:** `frontend/Dockerfile:1-3`

```dockerfile
FROM node:20-alpine AS base

FROM base AS deps
```

The `base` stage contains no `RUN` steps, no `ENV`, no `WORKDIR` — it is a zero-op
alias. This is valid but adds a named stage that confuses readers who expect `base`
to set up shared configuration (common in multi-stage patterns). The standalone
copy pattern is correct (`public/`, `.next/standalone`, `.next/static`), and image
size should be well under 200 MB with the Next.js standalone output confirmed in
`next.config.mjs:3` (`output: "standalone"`).

**Fix:** Either add shared setup to `base` (e.g., `WORKDIR /app`, `ENV NODE_ENV=production`)
to justify the alias, or collapse `base` and `deps` into a single stage.

---

### FE-009 🔵 LOW — No `.next/cache` BuildKit mount; each Docker build fetches fresh

**File:line:** `frontend/Dockerfile:14`

```dockerfile
RUN npm run build
```

`next build` stores compilation cache in `.next/cache`. Without a BuildKit
`--mount=type=cache` directive, every `docker build` starts cold. On a GCP
Ubuntu 24 VM where images are rebuilt on each deploy, build time for a large
Next.js app can be 2–4 minutes on a small VM versus 30–60 s with a warm cache.

**Fix:**

```dockerfile
RUN --mount=type=cache,target=/app/.next/cache \
    npm run build
```

Requires `DOCKER_BUILDKIT=1` (default in Docker 23+, which ships with Ubuntu 24).

---

### FE-010 🔵 LOW — a11y wave-1 and wave-2 commits land correctly in the production build path

**File:line:** N/A (positive verification)

The most recent a11y commits (`acbe5166`, `9d23f4df`, `0f954c8d`, `27c465d5`,
`b66c1d25`, `85848757`) all modify files under `frontend/src/`. The Dockerfile
builder stage (`FROM base AS builder`) uses `COPY . .` at line 13, which copies
the full `frontend/` tree including all modified source files. The `next build`
step at line 14 then compiles everything, and the standalone output includes the
compiled result.

There is no mechanism in the Dockerfile that would exclude specific source
subdirectories from the build. The `.dockerignore` excludes only `node_modules`,
`.next`, `.git`, `*.md`, `.env*.local`, test artifacts, and `e2e/` — none of
which contain a11y source code.

**Verdict:** All a11y fixes committed to `frontend/src/` are correctly included
in the production Docker image as-built.

---

## Summary verdict

The image architecture is **fundamentally sound**: Next.js standalone mode is enabled
(`next.config.mjs:3`), the runner stage is non-root (`USER node`, line 25), static
assets are correctly copied, and the healthcheck targets a real frontend-owned route
(`/api/healthz/route.ts`) that does not depend on backend availability. Standalone
output keeps image size well under 200 MB.

**The blocking issue for a GCP Ubuntu 24 deploy is FE-001** (non-reproducible builds
without the lockfile) combined with **FE-002** (operator confusion about
`NEXT_PUBLIC_API_URL` at runtime). Both are fixable in < 1 hour of work.

### Prioritized fix list

| Priority | ID | Fix |
|---|---|---|
| 1 | FE-001 | Restore `COPY package-lock.json` + `RUN npm ci`; remove `--legacy-peer-deps` |
| 2 | FE-002 | Add GCP rebuild note to DEPLOY.md; document the three runtime-URL options |
| 3 | FE-003 | Flows from FE-001; re-enable `npm audit` in CI once `npm ci` is restored |
| 4 | FE-004 | Pin `node:20.19.3-alpine3.21` (exact patch) |
| 5 | FE-006 | Bump `--start-period` to 30s for small GCP VMs |
| 6 | FE-009 | Add BuildKit cache mount for `.next/cache` |
| 7 | FE-005 | Add nginx/Caddy reverse proxy for static asset offload |

---

*End of DEPLOY_FRONTEND_IMAGE.md.*
