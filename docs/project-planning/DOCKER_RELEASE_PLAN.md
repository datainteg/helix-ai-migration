# Docker Release Plan

## Images

Official images:

- `datainteg/helix-ai-migration-frontend`
- `datainteg/helix-ai-migration-backend`
- `datainteg/helix-ai-migration-worker`

## Docker Compose Services

| Service | Purpose |
|---|---|
| `helix-ai-migration-frontend` | Next.js frontend |
| `helix-ai-migration-backend` | FastAPI backend |
| `helix-ai-migration-worker` | Temporal/agent worker |
| `postgres` | PostgreSQL metadata store |
| `redis` | Cache and short-lived state |
| `temporal` | Durable workflow orchestration |
| `temporal-ui` | Workflow inspection UI |

## Environment Variables

Required groups:

- App settings: `APP_ENV`, `APP_SECRET_KEY`
- Database: `DATABASE_URL`
- Redis: `REDIS_URL`
- Temporal: `TEMPORAL_ADDRESS`, `TEMPORAL_NAMESPACE`
- Security: `JWT_SECRET_KEY`, `ENCRYPTION_KEY`
- Artifact storage: `ARTIFACT_STORAGE_PROVIDER`, `LOCAL_ARTIFACT_STORAGE_PATH`
- LLM defaults: `DEFAULT_LLM_PROVIDER`, `DEFAULT_LLM_MODEL`
- Optional SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`

Secrets should be encrypted before storage and should not be printed in logs.

## Build Commands

```bash
docker build -t datainteg/helix-ai-migration-frontend:latest ./frontend
docker build -t datainteg/helix-ai-migration-backend:latest ./backend
docker build -t datainteg/helix-ai-migration-worker:latest ./worker
```

## Push Commands

```bash
docker push datainteg/helix-ai-migration-frontend:latest
docker push datainteg/helix-ai-migration-backend:latest
docker push datainteg/helix-ai-migration-worker:latest
```

Use version tags for releases:

```bash
docker tag datainteg/helix-ai-migration-frontend:latest datainteg/helix-ai-migration-frontend:v0.1.0
docker tag datainteg/helix-ai-migration-backend:latest datainteg/helix-ai-migration-backend:v0.1.0
docker tag datainteg/helix-ai-migration-worker:latest datainteg/helix-ai-migration-worker:v0.1.0
```

## Local Test

```bash
cp .env.example .env
docker compose config
docker compose up -d
docker compose ps
```

Expected URLs:

- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:8000`
- Temporal UI: `http://localhost:8233`

## Scaling Workers

```bash
docker compose up -d --scale helix-ai-migration-worker=3
```

## Release Checklist

- Compose config validates.
- Core services start.
- Backend health endpoint passes.
- Frontend loads.
- First admin setup works.
- PostgreSQL migrations apply.
- Artifact storage path is writable.
- LLM keys are encrypted and masked.
- Uploaded code is not executed.
- Docker image names match documentation.

## Related Architecture Docs

| Doc | What it covers |
|---|---|
| `DOCKER_GUIDE.md` | Image strategy, per-service build, env vars, scaling workers |
| `docs/deployment/INSTALLATION.md` | Quick start, first admin setup, troubleshooting, production notes |
| `docs/operations/CI_CD.md` | Build pipeline, Docker image build flow, release gates |
| `docs/storage/ARTIFACT_STORAGE.md` | Local artifact storage mount config |
| `README.md 15` | Full docker-compose.yml reference |
