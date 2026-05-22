# CI/CD

## Pull Request Checks

Planned PR checks:

- Markdown lint or docs consistency check
- Frontend lint, type-check, test, and build
- Backend lint, type-check, and tests
- Alembic migration check
- Agent schema validation tests
- Docker Compose config validation

## Main Branch

Main branch should run all PR checks and produce build artifacts. Docker images should use immutable release tags before publishing.

## Release Flow

- Update changelog or release notes.
- Tag release.
- Build frontend, backend, and worker images.
- Push:
  - `datainteg/helix-ai-migration-frontend`
  - `datainteg/helix-ai-migration-backend`
  - `datainteg/helix-ai-migration-worker`
- Verify Docker Compose install path.

