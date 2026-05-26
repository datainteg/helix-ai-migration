# Contributing to Helix Migration

Thanks for considering a contribution. This repo is Apache 2.0 — code,
docs, bug reports, and tested fixes all welcome.

## Where to contribute

| Area | Files |
|------|-------|
| AI agents / BMAD pipeline | `agents/` |
| Backend API | `backend/app/api/` |
| Backend services | `backend/app/services/` |
| Temporal worker | `worker/` |
| Frontend pages | `frontend/src/app/` |
| Built-in connectors | `connectors/` |
| Tests | `agents/tests/`, `backend/tests/` |
| Docs | `README.md`, `DEPLOY.md`, top-level `*.md` |

If you want to add a **new BMAD agent skill**, vendor it into
`agents/bmad/BMAD-METHOD/src/bmm-skills/<phase>/<skill>/` mirroring upstream
layout. Do NOT author prompts inline in Helix code — Helix loads SKILL.md
+ customize.toml as the source of truth.

## Local dev setup

### Prerequisites

- Docker 24+ and Docker Compose v2
- Python 3.11+ (for running tests / agents outside Docker)
- Node 20+ (for frontend dev outside Docker)

### Get the stack running

```bash
git clone https://github.com/datainteg/helix-ai-migration.git
cd helix-ai-migration

# Generate secrets (writes .env)
./scripts/generate-secrets.sh           # or .\scripts\generate-secrets.ps1

# Bring up the dev compose (hot reload + exposed ports for DB/Redis/Temporal)
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.build.yml up -d
docker compose exec backend alembic upgrade head

# Frontend dev mode (outside compose)
cd frontend
npm install
npm run dev                              # http://localhost:3000
```

### Run tests

```bash
# Agents tests (no DB required, runs against vendored BMAD)
python -m pytest agents/tests/ -v

# Backend tests (needs Postgres + Redis on localhost:5432/6379)
cd backend
python -m pytest tests/ -v

# Frontend Playwright tests (optional)
cd frontend
npx playwright install --with-deps chromium
npm run test:e2e
```

### Code style

- Python: Ruff (line length 120). Run `ruff check agents backend connectors worker` before opening a PR.
- TypeScript: ESLint via `npm run lint`. Tailwind classes via `tailwind-merge`.
- Commit messages: short imperative subject. No need for emoji prefixes.

### Dependency locking

`backend/requirements.txt` + `worker/requirements.txt` declare top-level deps
with version ranges. The pinned, fully-resolved versions used at build time
live in the corresponding `*.lock` files alongside them. **Docker builds
install from the lock, not the .txt.**

When you add or bump a top-level dep:

```bash
# Edit backend/requirements.txt (or worker/requirements.txt)
# Then regenerate the lock — runs pip-compile inside python:3.11-slim so the
# result matches the production image's Python version:
./scripts/lock-requirements.sh backend          # or `worker`, or omit for both

# Bump every pinned dep to its latest compatible version
./scripts/lock-requirements.sh --upgrade
```

Commit both the `.txt` AND the regenerated `.lock`. The Dockerfile falls
back to `.txt` if the lock is missing (with a printed warning), so the
build still works during a fresh fork's first commit.

## Pull request checklist

- [ ] Tests for new behavior (or rationale if no test is sensible)
- [ ] `agents/tests/` still passes (`pytest agents/tests/`)
- [ ] No new hardcoded prompts (use BMAD SKILL.md via `bmad_loader`)
- [ ] No new mock data in `frontend/` (use real backend endpoints + EmptyState)
- [ ] No real secrets committed (run `grep -r "sk-[a-zA-Z0-9]" .` before push)
- [ ] DEPLOY.md updated if you change env vars / ports / volumes
- [ ] README.md updated if you change repo layout or top-level features

## Architectural decisions worth knowing

1. **HelixBMAD class is the single entry point.** Backend and worker both
   import `from agents import HelixBMAD`. Don't reach into `agents.bmad.graph`
   or `agents.runtime.bmad_executor` from outside the package — extend
   `HelixBMAD` instead.

2. **BMAD-METHOD is the source of truth.** Personas, skill prompts, and
   customization layers all come from the vendored `agents/bmad/BMAD-METHOD/`
   tree. Helix does NOT author new agents.

3. **Workflow state lives in two places.** Temporal owns the durable
   execution state (queryable via Temporal SDK). The `WorkflowStep` table
   owns the persisted history (queryable via SQL + the
   `GET /agent-workflows/{id}` API). Both should agree.

4. **No telemetry by default.** Sentry / OpenTelemetry are optional
   (controlled by `SENTRY_DSN` / `OTEL_ENDPOINT` env vars). Default
   behavior is fully offline.

5. **Secrets are never returned via API.** Connector creds + LLM API keys
   are encrypted with Fernet (`secret_service.encrypt_value`) and only
   ever returned as masked previews.

6. **Frontend reads from API or shows EmptyState.** No mock-data fallbacks.
   `frontend/src/lib/mock-data.ts` was deleted on purpose; don't reintroduce.

## Reporting bugs

Open a GitHub issue with:
- Helix version (`docker compose images` output)
- Repro steps
- Logs from the failing service (`docker compose logs <service>`)
- Expected vs. actual behavior

For security issues, see [SECURITY.md](SECURITY.md) — please don't open
public issues for vulnerabilities.

## Versioning

Helix follows semver once we hit 1.0. Pre-1.0 we may make breaking changes
between minor versions; check CHANGELOG.md (when it exists) before
upgrading.

## License

By contributing you agree your contributions are licensed under Apache 2.0.
