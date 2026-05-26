# Installation Guide — DEPRECATED

> **This file is archived.** The canonical installation guide is
> [`DEPLOY.md`](../../DEPLOY.md) at the repository root.
>
> All content below is kept for historical reference only. Do not follow
> these instructions for new installs — they contain stale port numbers
> and a deprecated setup flow.

---

## Quick redirect

| You want to… | Go to… |
|---|---|
| Install Helix for the first time | [DEPLOY.md — One-click install](../../DEPLOY.md#one-click-install-recommended) |
| Deploy on a GCP VM | [DEPLOY.md — GCP one-VM deploy](../../DEPLOY.md#gcp-one-vm-deploy) |
| Upgrade an existing install | [DEPLOY.md — Updating Helix](../../DEPLOY.md#updating-helix) |
| Check Alembic migration history | [DEPLOY.md — Wave migration list](../../DEPLOY.md#wave-1--wave-2--wave-3-migration-list) |
| Post-upgrade verification | [DEPLOY.md — Post-upgrade verification](../../DEPLOY.md#post-upgrade-verification) |
| Install the CLI | `pip install helix-cli` or `pipx install helix-cli` |
| Install the Python SDK | `pip install helix-sdk` |
| Install the TypeScript SDK | `npm install @helix/sdk` |
| Bootstrap the first admin headlessly | `helix admin bootstrap --help` |

---

## Correct ports (wave-2+)

The ports listed in this file's original content were wrong. The correct
defaults are:

```text
Frontend:    http://localhost:3000   (was incorrectly listed as 8080)
Backend API: http://localhost:8000   (correct)
Temporal UI: http://localhost:8233   (accessible via SSH tunnel only)
```

---

## Environment variables

Core variables (set by `./scripts/generate-secrets.sh`):

```bash
APP_NAME=Helix Migration
APP_ENV=development
DATABASE_URL=postgresql://helix:<POSTGRES_PASSWORD>@postgres:5432/helix_metadata
REDIS_URL=redis://redis:6379/0
TEMPORAL_ADDRESS=temporal:7233
TEMPORAL_NAMESPACE=default
JWT_SECRET_KEY=<generated>
ENCRYPTION_KEY=<generated>
```

> **DATABASE_URL driver note:** always use the `postgresql://` prefix
> (psycopg2). The backend rewrites this to `postgresql+asyncpg://` for async
> contexts automatically. Do not set `postgresql+asyncpg://` manually.

Optional LLM provider keys (can also be configured via admin UI after first launch):

```bash
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_GEMINI_API_KEY=
DEEPSEEK_API_KEY=
OPENROUTER_API_KEY=
CUSTOM_LLM_BASE_URL=
CUSTOM_LLM_API_KEY=
```

---

## First admin setup (headless CLI — wave-2+)

```bash
pip install helix-cli

helix admin bootstrap \
  --api http://localhost:8000 \
  --email ops@example.com \
  --org-name "Acme Corp" \
  --accept-tos
# prompts for password; exits 0 on success or if already bootstrapped
```

Or use the UI wizard at `http://localhost:3000/setup/first-admin`.

---

*This file will not be updated further. All new documentation lives in
[DEPLOY.md](../../DEPLOY.md).*
