# Installation Guide

This guide describes the planned self-hosted installation flow for Helix Migration.

## Docker Quick Start

Prerequisites:

- Docker
- Docker Compose
- Git

Commands:

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

Core variables:

```bash
APP_NAME=Helix Migration
APP_ENV=development
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

Optional provider keys:

```bash
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_GEMINI_API_KEY=
DEEPSEEK_API_KEY=
OPENROUTER_API_KEY=
CUSTOM_LLM_BASE_URL=
CUSTOM_LLM_API_KEY=
```

Provider keys can also be configured later in the admin panel.

## First Admin Setup

1. Open the frontend.
2. Create the first admin user.
3. Create or confirm the organization.
4. Review system health.
5. Configure LLM provider settings.

First admin setup should only be available when no admin exists.

## LLM Setup

1. Open Admin -> LLM Providers.
2. Add provider.
3. Enter API key or custom model URL.
4. Test connection.
5. Select default model.
6. Configure agent-wise model mapping if needed.

Saved keys must be masked after save.

## Create First Project

1. Open Projects.
2. Create migration project.
3. Add subproject.
4. Add source and target metadata.
5. Enter requirement.
6. Start agent planning workflow.
7. Review and approve architecture output.
8. Continue to validation and reconciliation planning.

## Troubleshooting

| Issue | Check |
|---|---|
| Frontend unavailable | Check frontend container logs and port `8080` |
| Backend unavailable | Check backend logs and port `8000` |
| Database error | Check `DATABASE_URL` and PostgreSQL container |
| Temporal connection error | Check `TEMPORAL_ADDRESS` and Temporal container |
| LLM test fails | Check provider key, base URL, and model name |
| Key visible after save | Treat as security bug |

## Production Deployment Notes

- Replace all default secrets.
- Use TLS through a reverse proxy.
- Restrict PostgreSQL and Redis to private networks.
- Back up PostgreSQL.
- Monitor worker logs.
- Rotate API keys.
- Use strong `ENCRYPTION_KEY` and `JWT_SECRET_KEY`.
- Consider external PostgreSQL, Redis, and Temporal for larger deployments.

## Artifact Storage Configuration

MVP local artifact storage:

```bash
ARTIFACT_STORAGE_PROVIDER=local
ARTIFACT_STORAGE_PATH=./data/artifacts
MAX_UPLOAD_MB=25
```

PostgreSQL stores artifact metadata only. Uploaded/generated files should be stored in the configured artifact storage path. Future production deployments may use MinIO or S3-compatible storage.

## Encryption and Safe Execution

Required security variables:

```bash
ENCRYPTION_KEY=change_me_32_byte_key
JWT_SECRET_KEY=change_me
SAFE_EXECUTION_MODE=analysis_only
```

MVP must not execute arbitrary uploaded code. It should analyze code, review code, generate draft converted code, generate notebook structures, show diffs, and require human approval.

Future production notes:

- Use MinIO/S3-compatible artifact storage.
- Use Docker secrets, HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, or GCP Secret Manager.
- Restrict artifact storage access by organization and project.
- Back up PostgreSQL and artifact storage together.

## SMTP Notification Setup

SMTP can be configured after first admin setup from Admin -> Notifications -> SMTP.

Optional environment defaults:

```bash
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=Helix Migration
SMTP_USE_TLS=true
SMTP_USE_STARTTLS=true
```

If provided through environment variables, SMTP passwords should still be encrypted or moved into a supported secret manager before production use. The admin UI should show masked SMTP secrets and provide a test email action.
