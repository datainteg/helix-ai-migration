# Docker Guide

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

Helix Migration should be easy to run with Docker Compose and ready for future Kubernetes deployment.

## Image Strategy

Official images:

```text
datainteg/helix-ai-migration-frontend
datainteg/helix-ai-migration-backend
datainteg/helix-ai-migration-worker
```

Separate images allow independent scaling, deployment, logging, and upgrades.

## Services

| Service | Purpose |
|---|---|
| `helix-ai-migration-frontend` | Next.js web UI |
| `helix-ai-migration-backend` | FastAPI backend |
| `helix-ai-migration-worker` | Temporal workers and background jobs |
| `postgres` | Global metadata store |
| `redis` | Cache and short-lived state |
| `temporal` | Durable workflow engine |
| `temporal-ui` | Workflow observability |

## Frontend Image

The frontend image should:

- Build the Next.js app.
- Serve the production app.
- Accept `NEXT_PUBLIC_API_URL`.
- Avoid bundling secrets.

Build command:

```bash
docker build -t datainteg/helix-ai-migration-frontend:latest ./frontend
```

## Backend Image

The backend image should:

- Run FastAPI.
- Load environment from Docker Compose or secret manager.
- Connect to PostgreSQL, Redis, and Temporal.
- Run migrations through an explicit command or release job.

Build command:

```bash
docker build -t datainteg/helix-ai-migration-backend:latest ./backend
```

## Worker Image

The worker image should:

- Run Temporal workers.
- Execute agent workflows.
- Execute connector scans.
- Execute validation and reconciliation jobs.

Build command:

```bash
docker build -t datainteg/helix-ai-migration-worker:latest ./worker
```

## Docker Compose Flow

Expected quick start:

```bash
git clone https://github.com/datainteg/helix-ai-migration.git
cd helix-ai-migration
cp .env.example .env
docker compose up -d
```

Expected URLs:

```text
Frontend:    http://localhost:8080
Backend API: http://localhost:8000
Temporal UI: http://localhost:8233
```

## Environment Variables

Important variables:

```bash
APP_ENV=production
APP_SECRET_KEY=change_me
DATABASE_URL=postgresql://helix:helix_password@postgres:5432/helix_metadata
REDIS_URL=redis://redis:6379/0
TEMPORAL_ADDRESS=temporal:7233
TEMPORAL_NAMESPACE=default
JWT_SECRET_KEY=change_me
ENCRYPTION_KEY=change_me_32_byte_key
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4.1
```

Provider keys are optional during initial installation and can be configured through the admin panel after setup.

## Push Commands

```bash
docker push datainteg/helix-ai-migration-frontend:latest
docker push datainteg/helix-ai-migration-backend:latest
docker push datainteg/helix-ai-migration-worker:latest
```

Use immutable version tags for releases:

```bash
docker tag datainteg/helix-ai-migration-backend:latest datainteg/helix-ai-migration-backend:v0.1.0
```

## Scaling Workers

Workers should be horizontally scalable:

```bash
docker compose up -d --scale helix-ai-migration-worker=3
```

Temporal task queues should be designed so multiple workers can safely process jobs.

## Production Notes

- Use strong passwords.
- Use TLS behind a reverse proxy.
- Restrict PostgreSQL and Redis network access.
- Rotate encryption keys carefully.
- Back up PostgreSQL.
- Keep Docker images patched.
- Configure log retention.
- Do not put secrets in Git.

## Future Helm Chart

Future Helm support should include:

- Frontend deployment
- Backend deployment
- Worker deployment
- External PostgreSQL option
- External Redis option
- External Temporal option
- Secret management
- Ingress and TLS
- Worker replica scaling

## Artifact Storage in Docker

MVP should mount local artifact storage into backend and worker containers:

```text
ARTIFACT_STORAGE_PROVIDER=local
ARTIFACT_STORAGE_PATH=/app/data/artifacts
```

PostgreSQL stores artifact metadata only. Uploaded/generated files should be stored on the mounted filesystem for MVP. Future production deployments should support MinIO/S3-compatible storage.

## Secrets and Safe Execution

Docker deployments should use encrypted API key storage for MVP and prepare for Docker secrets or external secret managers later.

Safe execution rules:

- Do not execute arbitrary uploaded code in MVP.
- Analyze code and generate drafts only.
- Require human approval before production use.
- Future execution must use isolated containers, resource limits, network controls, and audit logs.

## Related Docs

| Doc | What it covers |
|---|---|
| `docs/deployment/INSTALLATION.md` | Quick start, first admin setup, troubleshooting, production notes |
| `docs/project-planning/DOCKER_RELEASE_PLAN.md` | Image build/push commands, release checklist |
| `docs/operations/CI_CD.md` | Docker image build pipeline, release gates |
| `docs/storage/ARTIFACT_STORAGE.md` | Local artifact storage mount config |
| `README.md 15` | Full docker-compose.yml reference |
| `SECURITY.md` | Docker security, secrets management |
