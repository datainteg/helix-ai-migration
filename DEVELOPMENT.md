# Development Guide

## Project Identity

| Item | Value |
|---|---|
| Product | Helix Migration |
| Repository | helix-ai-migration |
| Website | helix.datainteg.io |
| Tagline | Open-source AI-powered migration and validation platform. |
| Frontend image | datainteg/helix-ai-migration-frontend |
| Backend image | datainteg/helix-ai-migration-backend |
| Worker image | datainteg/helix-ai-migration-worker |

This guide describes how developers should work on Helix Migration once implementation begins. The repository is currently in planning and documentation phase.

## Prerequisites

Install:

- Git
- Docker and Docker Compose
- Node.js LTS
- Python 3.11 or newer
- PostgreSQL client tools
- Redis CLI, optional
- Temporal CLI, optional

## Repository Setup

```bash
git clone https://github.com/datainteg/helix-ai-migration.git
cd helix-ai-migration
```

Copy environment settings when `.env.example` exists:

```bash
cp .env.example .env
```

## Environment Setup

Expected local services:

| Service | Default |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |
| Temporal | localhost:7233 |
| Temporal UI | http://localhost:8233 |

Required environment groups:

- Application settings
- Database URL
- Redis URL
- Temporal address and namespace
- JWT secret
- Encryption key
- LLM provider keys or custom model URL

## Frontend Development

Expected command after frontend scaffolding:

```bash
cd frontend
npm install
npm run dev
```

Frontend stack:

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- React Flow
- Framer Motion

## Backend Development

Expected command after backend scaffolding:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Worker Development

Expected command after worker scaffolding:

```bash
cd worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Workers run agent workflows, connector jobs, validation jobs, reconciliation jobs, and long-running Temporal activities.

## Database Migrations

Alembic is the required migration tool.

Expected commands:

```bash
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
alembic downgrade -1
```

Rules:

- Never edit production databases manually.
- Keep migrations reviewable.
- Include indexes and constraints in migrations.
- Do not add columns for full customer business data unless explicitly configured.

## Docker Compose Development

Expected development flow:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Expected production-like flow:

```bash
docker compose up -d
```

Useful commands:

```bash
docker compose logs -f helix-ai-migration-backend
docker compose logs -f helix-ai-migration-worker
docker compose ps
docker compose down
```

## Testing

Expected commands after scaffolding:

```bash
cd frontend
npm test
```

```bash
cd backend
pytest
```

```bash
cd worker
pytest
```

Test coverage should include:

- API contracts
- RBAC checks
- Secret masking
- Agent output schema validation
- Connector interface behavior
- Validation and reconciliation calculations
- Artifact upload metadata and content hashing
- Code review and conversion output schemas
- Artifact approval workflow

## Linting and Formatting

Expected frontend commands:

```bash
npm run lint
npm run format
```

Expected Python commands:

```bash
ruff check .
ruff format .
mypy .
```

## Developer Workflow

1. Pull latest changes.
2. Create a focused branch.
3. Read relevant docs before editing.
4. Make a small change.
5. Add or update tests.
6. Run focused checks.
7. Update docs if behavior changes.
8. Open a pull request with screenshots or API examples when useful.

## Troubleshooting

| Symptom | Check |
|---|---|
| Backend cannot connect to database | Verify `DATABASE_URL`, container health, and PostgreSQL port |
| Worker cannot start | Verify Temporal address and backend settings |
| LLM test fails | Verify provider key, base URL, timeout, and provider status |
| API key appears in logs | Treat as security bug and fix immediately |
| Frontend API calls fail | Verify `NEXT_PUBLIC_API_URL` |
| Migrations fail | Check Alembic head, database state, and model imports |

## Developer Execution Development

Developer Execution work should keep uploaded code safe and versioned.

Rules:

- Do not execute uploaded code during analysis.
- Store artifact metadata and hashes in PostgreSQL.
- Use storage abstraction for file content.
- Treat generated code and notebook structures as draft until human approval.
- Link generated artifacts to agent outputs and validation/reconciliation requirements.

## Related Engineering Guides

- `TESTING.md` for test strategy, mock LLM provider, Temporal workflow tests, and artifact fixtures.
- `docs/operations/CI_CD.md` for pull request checks, Docker image build flow, and release gates.
- `docs/operations/BACKUP_RESTORE.md` for PostgreSQL and artifact storage backup coordination.
