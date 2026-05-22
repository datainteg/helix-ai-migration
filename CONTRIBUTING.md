# Contributing

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

Thank you for contributing to Helix Migration, an open-source AI-powered migration and validation platform.

## Ways to Contribute

- Documentation
- Frontend UI
- Backend APIs
- Agent workflows
- Connector implementations
- Validation and reconciliation rules
- Docker and deployment improvements
- Tests
- Example migration projects
- Developer workspace and Code Review Center UI
- Artifact metadata APIs
- Safe code analysis schemas
- Diff viewer components
- Validation template examples

## Setup

```bash
git clone https://github.com/datainteg/helix-ai-migration.git
cd helix-ai-migration
```

When implementation scaffolding exists, follow `DEVELOPMENT.md` for local setup.

## Branch Naming

Use focused branch names:

```text
docs/mvp-scope
frontend/project-workspace
backend/auth-api
agents/bmad-planning-flow
connectors/postgres-metadata-scan
validation/row-count-rules
```

## Commit Style

Use clear commits:

```text
docs: add MVP execution plan
feat: add project metadata API
fix: mask provider keys in API response
test: cover validation rule creation
```

## Pull Request Checklist

Before opening a PR:

- Read `README.md`.
- Confirm product naming is `Helix Migration`.
- Keep the change focused.
- Add or update tests when implementation changes.
- Update docs when behavior changes.
- Do not include secrets.
- Do not store full customer business data by default.
- Confirm API keys are masked.
- Confirm agent outputs are typed if touching agent runtime.
- Confirm generated code, notebook structures, validation plans, and reconciliation reports are described as drafts requiring human approval before production use.
- Do not add arbitrary uploaded-code execution.
- Include screenshots for frontend changes when useful.

## Issue Guidance

Good issues include:

- Clear problem statement
- Expected behavior
- Actual behavior
- Steps to reproduce
- Environment details
- Screenshots or logs when useful
- Security sensitivity if relevant

## Coding Standards

- TypeScript for frontend code.
- Python with Pydantic models for backend and agent contracts.
- SQLAlchemy or SQLModel for persistence.
- Alembic for migrations.
- Typed schemas for agent outputs.
- Consistent API response formats.
- Audit logs for sensitive actions.

## Documentation Standards

- Use Markdown headings clearly.
- Keep examples accurate.
- Do not make fake implementation claims.
- Keep docs aligned with `README.md`.
- Update related docs when architecture changes.

## Tests Required

Implementation PRs should include tests for:

- Backend API behavior
- RBAC and tenant separation
- Secret masking
- Database migrations
- Agent schema validation
- Connector contracts
- Validation and recon logic

## Good First Issue Areas

- Documentation improvements
- UI empty states
- API schema examples
- Connector metadata examples
- Validation rule examples
- Report templates
- Test coverage
