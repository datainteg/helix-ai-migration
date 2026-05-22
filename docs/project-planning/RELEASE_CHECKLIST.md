# Release Checklist

## Documentation

- README is current.
- `AGENTS.md` is current for Codex execution.
- Architecture and MVP docs match implementation.
- Installation guide matches Docker Compose.
- Security notes include secrets, RBAC, audit, artifact safety, and no arbitrary uploaded-code execution in MVP.
- API docs match available routes.
- Project planning docs are complete.

## Repository Artifacts

- `LICENSE` exists.
- `.env.example` exists.
- `docker-compose.yml` exists.
- `docker-compose.dev.yml` exists if development flow needs it.
- GitHub issue templates exist.
- GitHub Actions workflow exists.

## Docker

- Docker images build:
  - `datainteg/helix-ai-migration-frontend`
  - `datainteg/helix-ai-migration-backend`
  - `datainteg/helix-ai-migration-worker`
- `docker compose config` passes.
- Clean `docker compose up -d` works.
- Services recover after restart.
- Worker scale command is documented.

## Environment

- `.env.example` includes database, Redis, Temporal, JWT, encryption, artifact storage, LLM, and SMTP placeholders.
- No real secrets are committed.
- Required environment variables are documented.

## Product Demo

- First admin setup
- Login
- LLM provider setup
- Project creation
- Requirement intake
- BMAD workflow run
- Human approval
- Artifact upload
- Code analysis/review summary
- Draft diff and artifact approval
- Basic validation/recon report
- Audit logs
- System health

## Screenshots and Media

- Dashboard screenshot
- Admin LLM settings screenshot
- Project workspace screenshot
- Agent workflow screenshot
- Developer workspace screenshot
- Validation/recon report screenshot

## Security

- API keys encrypted before storage.
- Full keys are never displayed after save.
- Uploaded code is not executed.
- Artifact files are stored outside PostgreSQL.
- Audit logs exist for sensitive actions.
- RBAC checks pass.

## GitHub Release

- GitHub topics added.
- README badges added if available.
- First release notes drafted.
- Docker image tags published.
- Git tag created, for example `v0.1.0`.
- Known limitations documented.
