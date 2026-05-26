# Helix Migration — End-to-End First-Run Walkthrough on a Fresh Ubuntu 24 GCP VM

**Persona:** A stranger SSH'd into a brand-new `e2-medium` Ubuntu 24.04 GCP VM
with Docker Engine + Compose v2 pre-installed and nothing else. Their goal: a
working `/dashboard` view with the first admin user logged in.

**Scope:** every command from `git clone` to logged-in dashboard, every place
the experience breaks, every recovery story.

**Reference materials:** `README.md`, `setup.sh`, `setup.ps1`,
`scripts/generate-secrets.sh`, `docker-compose.yml`, `docker-compose.build.yml`,
`frontend/Dockerfile`, `backend/Dockerfile`, `.env.example`, `DEPLOY.md`,
`docs/review-v3/FIX_SUMMARY_V2.md`.

Note: there is no `docs/INSTALL.md` and no `docs/DEPLOY.md`. The deployment guide
lives at the repo root as `DEPLOY.md`. The README points to "DEPLOY.md" which
resolves correctly from the root, but anyone who navigated into `docs/` first
will not find it there.

---

## Step 1 — `git clone`

### What the README tells the operator

README "Quick start" block (lines 48-66) literally contains the placeholder URL:

```
git clone https://github.com/<your-fork>/helix-ai-migration.git
```

`DEPLOY.md` repeats the same placeholder on line 28 and line 62.

### Friction

- **`<your-fork>` is not a real URL.** A first-time operator has to know to
  swap in `datainteg/helix-ai-migration` (or whatever the canonical org turns
  out to be). The README does not commit to a canonical fork name anywhere.
- The repo name on disk is `helix-ai-migration/`, but the README's prose on
  line 8 says "Clone the repo, run `docker compose up`", which is misleadingly
  short — `docker compose up` alone won't work because `.env` does not exist
  yet (see Step 3).

### Failure modes

- Operator copy-pastes the literal `<your-fork>` string → `Repository not found`.
- Operator clones with an unfamiliar HTTPS token setup on the VM and hits an
  auth prompt that hangs the SSH session (Git defaults to interactive prompt).

### STOP-1

**The repo URL is not real.** Until the README hard-codes the canonical org
(or the project sets up a vanity URL such as `helix.dev/get`), every operator
has to ask a human first. This blocks any unattended "curl | bash" one-liner.

### Recovery

`git clone <real-url>` and start over. No persisted state, safe to retry.

### Elapsed (cumulative)

~30 s if the operator already knows the URL; otherwise indeterminate.

---

## Step 2 — `cd helix-ai-migration && cp .env.example .env`

### What's expected

Two valid paths exist, and the docs disagree about which is canonical:

- **`DEPLOY.md` "One-click install" (lines 25-33):** run `./setup.sh`, which
  copies `.env.example` → `.env` itself (verified in `setup.sh` lines 110-120).
- **`DEPLOY.md` "Manual install" (lines 58-88):** operator manually runs
  `./scripts/generate-secrets.sh`, which also self-heals — if `.env` is
  missing it copies from `.env.example` (`scripts/generate-secrets.sh` lines
  85-93).
- **README "Quick start" (lines 48-66):** does NOT mention `setup.sh` at all.
  It tells the operator to run `generate-secrets.sh`, then `docker compose
  build`, then `up -d`, then `alembic upgrade head` manually. This is the
  legacy path.

### Friction

- **Three different "blessed" first-run paths** across three places:
  - README quick-start: manual 4-step sequence.
  - `DEPLOY.md` "One-click": `./setup.sh`.
  - `DEPLOY.md` "Manual": same as README quick-start.
- A first-timer skimming the README will never learn that `setup.sh` exists.
- `cp .env.example .env` itself is fine, but operators following the manual
  path may forget that `generate-secrets.sh` does this for them and run both,
  which is benign but adds confusion.

### Failure modes

- Operator forgets `cp` step → `docker compose up` aborts because
  `POSTGRES_PASSWORD` is required (the compose file enforces `${VAR:?error}`).
- Operator edits `.env.example` instead of `.env` (common mistake) → secrets
  generation writes to `.env`, but their custom CORS / API URL changes are
  ignored.

### Recovery

Safe to re-run. `cp -n .env.example .env` would be a safer default.

### Elapsed

~5 s.

---

## Step 3 — `./setup.sh`

### What it does (verified against `setup.sh`)

1. **Preflight:** checks `docker`, `docker compose version`, `docker info`.
2. **`.env` provisioning:** `cp .env.example .env` if missing.
3. **Secret generation:** runs `scripts/generate-secrets.sh` (fills
   `POSTGRES_PASSWORD`, `APP_SECRET_KEY`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`,
   `AUDIT_HMAC_KEY`, `TEMPORAL_UI_PASSWORD`, `DATABASE_URL`).
4. **Required-key audit:** greps `.env` for `POSTGRES_PASSWORD`,
   `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, `AUDIT_HMAC_KEY` — non-empty.
5. **Builds images** via `docker compose -f docker-compose.yml -f
   docker-compose.build.yml build` (5-10 min first time).
6. **Starts core:** Postgres + Redis + Temporal, polls `pg_isready` up to 60 s.
7. **Starts apps:** backend, worker, frontend. Backend `CMD` is `alembic
   upgrade head && uvicorn ...` (verified `backend/Dockerfile` line 42), so
   migrations run automatically inside the container.
8. **Readiness gate:** polls `http://localhost:8000/api/v1/readyz` up to 120 s.
9. **Prints URLs.**

### Flags

`--rebuild`, `--rotate-secrets`, `--down`, `--nuke`. No `--non-interactive`
flag exists, but the only interactive prompt is the destructive `--nuke`
confirmation — so the default `./setup.sh` IS non-interactive and safe for
automation.

### Friction

- **First-run build is 5-10 min, sometimes 15+** on an `e2-medium` (2 vCPU,
  4 GB RAM). README does not warn about CPU pressure during `npm install
  --legacy-peer-deps`. The frontend Dockerfile uses `--legacy-peer-deps`,
  which is a smell that suggests dependency conflicts may surface during
  future Node bumps.
- **`NEXT_PUBLIC_API_URL` is baked at build time** (`frontend/Dockerfile`
  lines 9-10, `docker-compose.build.yml` line 27). On a GCP VM, the default
  `.env.example` value `http://localhost:8000` is wrong — the operator's
  browser is on their laptop, not the VM. They need to set
  `NEXT_PUBLIC_API_URL=http://<VM-public-IP>:8000` BEFORE `setup.sh` builds
  the frontend image. `setup.sh` does not prompt for this. `DEPLOY.md` line
  144 mentions it; the README does not.
- **`/api/v1/readyz` health-gate is generous (120 s) but not infinite.** On
  a slow VM during cold-start (first-ever container pull + Postgres bootstrap
  + alembic running 28 migrations), 120 s can be tight.
- The 4 GB RAM minimum from `DEPLOY.md` is the floor; `e2-medium` is exactly
  4 GB. With Postgres (1 GB), Temporal (1 GB), backend (1 GB), worker (1 GB),
  frontend (512 MB), the operator is over-committed by ~700 MB on a `e2-medium`
  before the OS overhead. Docker will OOM-kill worker or frontend under load.
- **Repeat-clicker frustration:** when `setup.sh` fails at the readyz poll, it
  prints "tail logs" but does not auto-tail. Operator must remember the exact
  `docker compose logs --tail=80 backend` invocation.

### Failure modes

- **Docker daemon not running** (rare on GCP-prebuilt Docker images): script
  exits cleanly with `Start Docker Desktop or 'sudo systemctl start docker'`.
- **`docker compose` v1 only** (old VMs): script catches via `docker compose
  version` and tells the operator to install `docker-compose-plugin`. Good.
- **OOM during build:** frontend build runs `npm install` + `npm run build`
  inside a 4 GB VM. If Postgres/Redis/Temporal were already started, build
  competes for RAM with running containers. `setup.sh` does NOT start them
  until step 6, so the first run is fine, but a `--rebuild` against a running
  stack will OOM the worker.
- **Wrong `NEXT_PUBLIC_API_URL`:** image builds fine, stack comes up green,
  browser opens `http://<VM-IP>:3000`, login fails with "Failed to fetch"
  because the bundled JS calls `http://localhost:8000` which doesn't exist on
  the operator's laptop. Recovery requires editing `.env`, then `docker
  compose -f docker-compose.yml -f docker-compose.build.yml build frontend`
  + `docker compose up -d frontend`. The "Troubleshooting" section of
  `DEPLOY.md` line 334 calls this out, but it's the #1 silent failure.

### STOP-2

**`NEXT_PUBLIC_API_URL` is the single biggest first-run footgun for any non-localhost deploy.** `setup.sh` does not prompt for it, the README does
not mention it, and the failure mode is a silent "Failed to fetch" in the
browser console after a green ./setup.sh.

### Recovery

- If migrations fail: `docker compose logs backend`, fix, `docker compose
  restart backend` (alembic re-runs on every backend start).
- If readyz times out: `docker compose ps` to see who crashed, `docker
  compose logs <svc>`. Usually Temporal is slow on cold start; just re-run
  `./setup.sh` and it skips already-built work.
- If frontend image was built with wrong API URL: `NEXT_PUBLIC_API_URL=http://<ip>:8000 docker compose -f docker-compose.yml -f
  docker-compose.build.yml build frontend && docker compose up -d frontend`.

### Elapsed (cumulative)

~12 minutes if everything is happy (image build dominates).

---

## Step 4 — `docker compose up -d`

### Automatic or manual?

**Automatic** when `setup.sh` is used (Step 3 starts the stack itself). The
README's quick-start path requires it manually.

### Friction

- The README and `DEPLOY.md` manual install both say `docker compose up -d`
  but do not include the build overlay. The image names
  `helix/backend:latest`, `helix/worker:latest`, `helix/frontend:latest`
  resolve to local images only — without `-f docker-compose.build.yml build`
  first, `docker compose up -d` will try to `pull` and fail with `image not
  found` (unless `HELIX_IMAGE_PREFIX` was set to a real registry, which is
  documented but easy to miss).
- `DEPLOY.md` line 80 contradicts itself: shows `docker compose up -d` after a
  build that was scoped to the overlay — operator may run `up` without the
  overlay and end up with services from `docker-compose.yml` that pull instead
  of build (which is wrong for the local case).

### Failure modes

- "Image not found" because operator skipped the build overlay.
- Race: `worker` starts before `temporal` is healthy. Compose only uses
  `service_started` (not `service_healthy`) for the worker→temporal edge.
  Worker container restart-loops for ~30 s, then settles. `DEPLOY.md`
  troubleshooting (line 326) calls this out.

### Recovery

`docker compose -f docker-compose.yml -f docker-compose.build.yml build &&
docker compose up -d`. No data loss.

### Elapsed (cumulative)

+15 s if images are already built.

---

## Step 5 — `alembic upgrade head`

### Automatic or manual?

**Automatic.** `backend/Dockerfile` line 42:

```dockerfile
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Every backend container start re-runs the migrations. Idempotent. The
README and `DEPLOY.md` both instruct the operator to run it manually
(`docker compose exec backend alembic upgrade head`) — but on a fresh
install it is a no-op because the container already did it on boot. This is
not wrong, just redundant and a source of operator confusion ("did it work?").

### The wave-1 + wave-2 new migrations

The fresh-install path picks these up automatically because the container
runs `alembic upgrade head` on every start. The 5 migrations explicitly
called out in the task description are all present in
`backend/alembic/versions/`:

- `eadec18c9cfc_workflow_steps_parsed_output_jsonb.py` — wave-1 DI fix
- `8f881cfc333e_identity_uuid_to_string36.py` — wave-1 identity rebuild
- `p7q8r9s0t1u2_perf_missing_indexes.py` — wave-1 perf fix
- `2af2b45b4051_dek_partial_unique_active.py` — wave-2 DEK fix (DI-C1)
- `q8r9s0t1u2v3_encrypt_extra_config_secrets.py` — wave-2 SEC-010

`FIX_SUMMARY_V2.md` §7 operator pre-flight (line 223-229) instructs:
> "2. `cd backend && alembic upgrade head` (applies wave-2 migrations:
> `2af2b45b4051` DEK partial-unique, `q8r9s0t1u2v3` extra_config rewrap)"

This is correct guidance for an **upgrading** operator (someone who already
had Helix running and pulled latest). For a **fresh install**, the
backend container's startup CMD handles it. The wave-2 doc does not
distinguish these two cases. New operators will be confused; existing
operators will be confused why nothing in the README mentions the
container-side migration.

### Friction

- **Three places to "run migrations,"** all of which converge to the same
  `alembic upgrade head`: backend Dockerfile CMD (auto), `setup.sh` (auto via
  CMD), `DEPLOY.md` manual install Step 6 (manual). Operator does not know
  which one ran or whether they all ran.
- **Upgrade flow is under-documented.** `DEPLOY.md` "Updating Helix" (lines
  302-310) tells operators to run `docker compose exec backend alembic
  upgrade head` after `up -d` — but the container will have already run it
  on start. The race here is benign (alembic is idempotent under its lock)
  but unnerving to watch in logs.

### Failure modes

- **Migration fails mid-stack-start.** Backend container restart-loops.
  Worker can't reach a healthy backend. Recovery: `docker compose logs
  backend | grep -i alembic` to find the offending revision, then
  `docker compose exec backend alembic downgrade <prev>` or restore from
  Postgres backup. No automated rollback story exists.
- **`8f881cfc333e_identity_uuid_to_string36`** (wave-1) is a destructive
  identity-column type swap. On an upgrade of an existing DB with data, this
  needs a backup first — not mentioned in `FIX_SUMMARY_V2.md` operator
  pre-flight. Fresh installs are fine.

### Recovery

If forward-broken: `docker compose down`, restore Postgres dump, `docker
compose up -d`. `DEPLOY.md` "Postgres backup" (line 207) covers the dump
side but not "you should take one before upgrading."

### Elapsed (cumulative)

+5-20 s during backend container start (28 migrations).

---

## Step 6 — First-admin user creation

### Path

`/setup/first-admin` — UI wizard. Verified in
`frontend/src/app/setup/first-admin/page.tsx` (6-step React wizard):

0. Workspace name (POSTs to `/api/v1/auth/first-admin`, returns JWT)
1. LLM provider (POSTs to `/api/v1/llm-providers` for each chosen provider)
2. Agent routing (PUT to `/api/v1/llm-agent-mappings`, atomic replace)
3. First connection (collected locally, persisted in step 4)
4. First project (POST `/api/v1/projects`, then `/sources`)
5. Launch — "Open Helix Console" → `/dashboard`

Backend endpoint: `POST /api/v1/auth/first-admin` (verified
`backend/app/api/auth.py:29-36`). Returns `TokenResponse`, then frontend
stores the JWT in `localStorage`.

### Friction

- **No CLI fallback.** If the frontend is broken or the operator runs a
  headless deploy (CI smoke test, scripted install), there is no
  `helix bootstrap-admin --email ... --password ...` equivalent. The CLI
  bumped to v0.2.0 (FIX_SUMMARY_V2.md §2.3) but does not appear to ship a
  first-admin command.
- **Operator must know the URL.** `setup.sh` prints the URL at the end
  (`http://localhost:3000/setup/first-admin`), but the README only sends them
  to `http://localhost:3000`. Top-level `/` on the frontend does not (as far
  as I can tell from a brief inspection) auto-redirect to the wizard when
  no admin exists — operator who lands on `/` may see a sign-in form and not
  know there is a wizard.
- **`NEXT_PUBLIC_API_URL` revisited.** Step 0 of the wizard does
  `fetch(\`${API_BASE}/api/v1/auth/first-admin\`)` where `API_BASE` is read
  at JS bundle build time. If it points at `localhost:8000` and the operator
  is on a laptop hitting the VM, step 0 fails silently with "Failed to fetch."

### Failure modes

- **Wizard step 0 succeeds, page reload happens, operator can't continue.**
  The JWT is stored in `localStorage`, so resuming the wizard works — but if
  the operator clears cookies/storage, they cannot rerun the first-admin
  endpoint (it 409s because an admin already exists). Recovery: nuke the
  database (`./setup.sh --nuke`) or manually DELETE from `users` and
  `organizations`.
- **LLM provider step fails because the API key is wrong.** The wizard can
  retry, but if the operator clicks "Next" past a 400, they may land on the
  agent-routing step with no providers to route to.

### Recovery

`./setup.sh --nuke` and restart from Step 3. Destructive — wipes all data.

### Elapsed (cumulative)

+2-5 minutes (operator typing org name, pasting API keys, choosing models).

---

## Step 7 — LLM provider bootstrap

### Path

UI step 1 of the first-admin wizard. **Not env-var only.** `.env.example`
lines 71-78 list `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` etc. but
`.env.example` line 67 explicitly says "Operators configure providers + API
keys via the admin UI after first launch. These defaults only seed the
dropdown — they are not used at runtime." So env-vars are decorative only.

### Friction

- **No backend smoke test on save.** If the operator pastes a wrong API key,
  the wizard accepts it. The first BMAD agent call (Step 9 below) fails with
  401/403 from the upstream provider. There IS a "test connection" endpoint
  per `FIX_SUMMARY_V2.md` §3.1 — but it's not clear the wizard calls it.
- **6 agents × 1 provider = simplest mapping**, but the wizard forces an
  explicit choice for all 6 agents even when the operator wants "use the
  default for everything." Friction for first-runners; power-feature later.
- **Cost rate overrides** (`HELIX_PROVIDER_RATES_JSON`, .env line 131) are
  documented in .env.example but not surfaced in the UI. Operators with
  custom Anthropic/OpenAI contracts won't know to set them and will see
  inflated cost estimates.

### Failure modes

- API key 401 → silent until Step 9 first BMAD agent run.
- Provider mapping references a model the provider doesn't have (e.g.
  `claude-opus-4-7` on a key that only has Sonnet access) → first run of
  Mary/Winston returns 404.

### Recovery

`/admin/llm-settings` and `/admin/agent-mapping` are reachable after the
wizard. Re-paste key, re-map agents.

### Elapsed (cumulative)

+1-3 minutes.

---

## Step 8 — `/dashboard` first paint

### What greets the operator

After clicking "Open Helix Console" in step 5 of the wizard, the operator
lands on `/dashboard`. The auth context already has the JWT from step 0.

### Friction

- **Mostly mock data.** Per the memory: "Next.js 14 App Router, 25 pages,
  mostly mock data, agent canvas hardcoded." A first-run dashboard with
  zero migrations may show stub charts or empty states that are not yet
  wired to the freshly-created project from step 4.
- **No "welcome banner"** that says "Project X was created. Click here to
  open it."
- **Metadata title** — the wave-2 a11y fix (FIX_SUMMARY_V2.md §3.6) ensures
  the `<title>` element renders. So at least the browser tab shows "Dashboard
  · Helix" which is the smoke-test signal.

### Failure modes

- **JWT decoded async path broken** (wave-1 partial / wave-2 §3.5 closed) —
  if for some reason a stale wave-1-era worker is still running, calls to
  `/api/v1/sprints` or `/api/v1/agent-workflows` may hang the event loop.
  Wave-2 closed this. New operators are safe.
- **`Failed to fetch`** on dashboard widgets: same root cause as Step 6 —
  baked-in `NEXT_PUBLIC_API_URL` doesn't match the VM's reachable address.

### Recovery

Rebuild frontend image with correct `NEXT_PUBLIC_API_URL`.

### Elapsed (cumulative)

+5 s for first paint.

---

## Step 9 — Create first project → kick BMAD workflow

### Does it actually run?

The wizard's step 4 already created a project. To kick the 13-node BMAD
pipeline, the operator navigates to that project (or to `/projects/new` for
another) and clicks "Generate Plan" (per `DEPLOY.md` line 94).

### Friction

- **Worker must be alive.** `docker compose ps worker` must show `Up`. The
  worker depends on `backend` healthy + `temporal` started. Cold-start race
  (Step 4 above) usually settles within 60 s.
- **Temporal task queue must be registered.** Per memory:
  "Temporal worker; only monolithic workflow registered; per-node broken."
  This is a known gap. The 13-node per-node workflow may not actually run
  end-to-end on a fresh install. The monolithic fallback should work.
- **Approval gate.** Step 7 (winston_readiness) → approval_gate. The pipeline
  pauses up to 48 h waiting for a human signal. New operators may not realize
  the workflow is "stuck" — it's actually waiting for them.

### Failure modes

- LLM key 401 (Step 7 above) → first agent (Mary) fails. Workflow goes to
  `failed` state. Per `DEPLOY.md` troubleshooting, the operator can re-trigger
  from `/agents`.
- Worker container OOM during LangGraph init on a 4 GB VM (Step 3 friction).
- Approval gate timeout (48 h) → workflow ends with `status=pending`.

### Recovery

`/agents` UI page should expose "Retry," "Approve," "Reject" buttons. If not
wired (mock-data risk), operator falls back to the Temporal UI:
`docker compose --profile debug up -d temporal-ui`, then SSH-tunnel to
`localhost:8233`.

### Elapsed (cumulative)

+30 s to kick + N minutes for the 7 pre-approval agents to run (depends on
LLM latency + model size, typically 3-10 min).

---

## Step 10 — Slack / webhook integration

### Skippable?

**Yes.** `.env.example` lines 117-125 make `SLACK_SIGNING_SECRET` and the
user-mapping vars explicitly optional with a "Leave blank to disable the
receiver" comment. The first-admin wizard does not include Slack.

### Friction

- Operators evaluating Helix won't know Slack is supported unless they
  read `.env.example` or wave-2 §3.3. There's no "Integrations" tab in the
  wizard.
- SMTP setup (.env lines 100-107) is similarly skippable. But without SMTP,
  user invitations don't work, password resets don't work — and there's no
  "you need to configure SMTP" nag when an admin tries to invite a teammate.

### Failure modes

- Operator copies a Slack signing secret incorrectly → 401 on every Slack
  callback. Logged but invisible to the UI.

### Recovery

Add to `.env`, `docker compose restart backend worker`. Non-destructive.

### Elapsed (cumulative)

Zero — explicitly skipped for first run.

---

## Cross-cutting: things the operator must do that the docs scatter

### SDK + CLI v0.2.0 install

Wave-2 §2.3 bumped Python SDK + CLI from 0.1.0 → 0.2.0. Operator pre-flight
(§7 line 229) says:
> `pip install -e ./sdk/python ./cli` (v0.2.0)

**Verdict:** this is for SDK/CLI developers and integration testers, NOT for
the first-run web operator. A pure web-UI operator never touches `pip`. The
docs don't make this distinction. README and `DEPLOY.md` don't mention the
SDK install at all. Fine for first-run; documentation gap for SDK consumers.

### Frontend `npm install && npm run build`

`FIX_SUMMARY_V2.md` §7 line 228 says "`cd frontend && npm install && npm run
build`". **This is wrong for the docker-compose path.** The frontend
container is built from `frontend/Dockerfile` which does `npm install
--legacy-peer-deps` + `npm run build` inside the image. Operators following
the compose path never run npm on the host. The wave-2 doc was written from
the perspective of a contributor running the dev server locally.

### `npm run build:og`

The OG image script exists at `website/scripts/rasterise-og.mjs` and is
`npm run build:og` in `website/package.json` line 12. This is the marketing
site, not the app. **First-run operators never touch this.** It's the job of
whoever publishes the website to `helix.dev` (or wherever). Documentation
gap only matters for whoever owns the website.

### `pip install -e .`

Same as SDK above — not required for first-run.

---

## Time-to-first-dashboard estimate

| Stage | Best case | Realistic (e2-medium GCP VM) |
|-------|-----------|------------------------------|
| `git clone` | 30 s | 1 min (if URL is known) |
| `cp .env.example .env` | 5 s | 5 s |
| `setup.sh` preflight + secrets | 10 s | 10 s |
| `setup.sh` image build (first time) | 5 min | **12 min** (4 GB RAM is tight; npm install dominates) |
| `setup.sh` start + Postgres ready | 30 s | 90 s |
| `setup.sh` migrations + readyz | 20 s | 60 s |
| `/setup/first-admin` wizard (6 steps) | 2 min | 5 min (paste API keys, choose models) |
| `/dashboard` first paint | 5 s | 5 s |
| **Total** | **~8 min** | **~20 min** |

If `NEXT_PUBLIC_API_URL` is wrong on first build, add 8-12 minutes for the
frontend rebuild + restart.

---

## Top 5 friction points

1. **`NEXT_PUBLIC_API_URL` baked at build time, defaults to `localhost`,
   not prompted by `setup.sh`.** Any non-localhost deploy (every GCP VM!)
   silently breaks the frontend with a generic "Failed to fetch." Fix:
   `setup.sh` should detect non-localhost (read the VM's external IP or
   take an arg) and either prompt or set `NEXT_PUBLIC_API_URL`
   automatically before the frontend build.
2. **The repo URL in README is `https://github.com/<your-fork>/...`** — a
   placeholder. No canonical clone URL exists. Blocks any unattended install.
3. **Three different "first-run paths" in README vs. DEPLOY.md.** README
   quick-start (4 manual steps), DEPLOY.md one-click (`./setup.sh`),
   DEPLOY.md manual (4 manual steps again). README doesn't mention
   `setup.sh` at all. Fix: collapse to ONE path in README, mark the rest
   as "expert mode."
4. **No CLI bootstrap for first-admin.** Headless / scripted installs cannot
   complete without a browser. Blocks CI smoke tests and Terraform-style
   "infrastructure as code" provisioning. Fix: add `helix admin bootstrap`
   or `python -m app.scripts.bootstrap_admin --email X --password Y`.
5. **4 GB RAM floor is too tight for `e2-medium`.** Compose memory limits
   sum to 4.8 GB before OS overhead. A first-run on the documented minimum
   spec WILL OOM under load. Fix: bump README "Hardware floor" to 6 GB and
   recommend `e2-standard-2` (8 GB) on GCP.

---

## Recommended one-liner

```bash
# NOT YET SAFE — see caveats below.
curl -fsSL https://helix.dev/install.sh | bash
```

**Why it's not safe today:**

1. The clone URL is a placeholder (`<your-fork>`). No canonical resolution.
2. `NEXT_PUBLIC_API_URL` cannot be inferred from a piped script — operator
   must answer "what is the public URL clients will use to reach this VM?"
3. First-admin creation requires a browser session — no CLI fallback.
4. The 4 GB RAM minimum + 5-10 min build is too long to run unattended
   without progress UI.
5. There is no installer script shipped at any URL today — `install.sh`
   would have to be authored.

**Path to a real one-liner** (estimated 3-5 days of work):

```bash
curl -fsSL https://helix.dev/install.sh | bash -s -- \
  --public-url https://helix.example.com \
  --admin-email admin@example.com \
  --admin-password $(openssl rand -hex 16)
```

That installer would need to:
1. Detect Docker + install if missing.
2. Clone the canonical repo (resolved by `helix.dev/install.sh`).
3. Write `.env` with `NEXT_PUBLIC_API_URL=$PUBLIC_URL` and
   `CORS_ORIGINS=["$PUBLIC_URL"]` baked in.
4. Run `./setup.sh`.
5. Call a new `helix admin bootstrap` CLI command to create the first admin
   non-interactively, then print the login URL + temp password.
6. Optionally configure Caddy/Traefik for TLS termination.

---

## Verdict

**⚠️ Needs operator hand-holding.**

Helix is closer to "1-click" than most OSS platforms in this category:
`./setup.sh` is genuinely well-built (preflight, secret generation,
readiness gates, helpful error messages), the alembic migrations run
automatically on backend boot (no manual step), and the first-admin
wizard is a real 6-step UI (not a CLI).

But three things gate the "✅ 1-click" rating:

- The repo URL placeholder.
- `NEXT_PUBLIC_API_URL` baked-at-build-time silent-fail on any
  non-localhost deploy.
- No CLI / non-interactive admin bootstrap.

Close all three and add the installer script + canonical clone URL, and
Helix earns the ✅ "1-click ready" badge. As of today, a new operator on a
fresh Ubuntu 24 GCP VM can reach `/dashboard` in ~20 minutes IF they
already know the repo URL and remember to set `NEXT_PUBLIC_API_URL`. If
either of those slips, they hit STOP-1 or STOP-2 and need a human to
unblock them.
