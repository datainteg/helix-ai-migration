# Security policy

Helix Migration is self-hosted, so the security posture is mostly in
operators' hands. This document covers what Helix does for you, what it
does NOT do, and how to report a vulnerability.

## Reporting a vulnerability

**Please do not open a public GitHub issue.**

Email: `security@datainteg.io` (replace with your actual security contact
before publishing).

Include:
- Helix version (commit SHA or image tag)
- Affected component (backend / worker / frontend / connector / agent)
- Repro steps
- Expected severity (low / medium / high / critical)
- Whether the issue is already public

We aim to acknowledge within 72 hours and ship a fix or mitigation within
14 days for high-severity issues. Credit is given in the release notes
unless you ask otherwise.

## What Helix does

| Control | How |
|---------|-----|
| **JWT auth** | HS256 with `JWT_SECRET_KEY`; Redis-backed revocation list for logout/rotate |
| **RBAC** | 6 system roles × 18 permissions; per-org isolation enforced at query level |
| **API key encryption** | LLM provider keys stored Fernet-encrypted (`secret_service`) |
| **Connector credential encryption** | DB / S3 / cloud creds encrypted at rest (Fernet); masked previews on read |
| **Audit log** | Every mutation writes to `audit_log` with HMAC chain for tamper detection |
| **Rate limiting** | SlowAPI on auth, connector test, discover, superadmin impersonate |
| **CORS allowlist** | Production rejects wildcard origins + regex; explicit list required |
| **Secrets fail-fast** | Server refuses to boot with `change_me` defaults when `APP_ENV=production` |
| **Path traversal protection** | Artifact reads guarded by per-workflow allowlist |
| **Workflow org isolation** | All `/agent-workflows/{id}` endpoints validate workflow belongs to caller's org |
| **Per-request body size limit** | `MAX_UPLOAD_MB` rejects oversize requests at middleware layer |

## What Helix does NOT do (operator responsibilities)

| Gap | Mitigation |
|-----|------------|
| **No TLS termination** | Run behind your own reverse proxy (Caddy / Traefik / nginx) for HTTPS |
| **No DDoS protection** | Use Cloudflare / your cloud's WAF for layer-7 protection |
| **Postgres + Redis open inside the Docker network** | Don't run untrusted code in the same Docker network |
| **Temporal UI has no auth in default compose** | Firewall port 8233 OR proxy behind basic auth (see DEPLOY.md) |
| **No automated backups** | Schedule `pg_dump` cron — see [DEPLOY.md](DEPLOY.md) for example |
| **No malware scanning on uploads** | Add ClamAV scanning if you accept untrusted artifacts |
| **No code execution sandbox** | `SAFE_EXECUTION_MODE=analysis_only` by default — never set to `execute` |

## Hardening checklist for production

1. Run `./scripts/generate-secrets.sh` (or `.ps1`) — never ship `change_me` defaults.
2. Set `APP_ENV=production` in `.env` — this enables strict secret validation at boot.
3. Set `CORS_ORIGINS` to your real frontend domain(s); leave `CORS_ORIGIN_REGEX` empty.
4. Firewall ports 5432 (Postgres), 6379 (Redis), 7233 (Temporal), 8233 (Temporal UI) to internal access only.
5. Put your domain behind TLS via a reverse proxy.
6. Schedule Postgres backups (`pg_dump | gzip | s3 cp -`).
7. Mount `helix_postgres_data` and `helix_artifacts` to host-managed paths or cloud volumes.
8. Subscribe to GitHub releases for security advisories.

## Threat model — out of scope

Helix is a self-hosted tool. The following are NOT in our threat model:
- Adversarial workflow inputs from authenticated users (we trust your
  RBAC enforcement; configure roles correctly).
- Compromise of the host OS or the Docker daemon.
- Side-channel attacks on the LLM provider (we forward your prompt; the
  provider sees it).
- Prompt injection by malicious requirement text (the human approval gate
  is the safety control here — don't auto-approve).

## Dependencies

We monitor:
- `pip-audit` on backend/worker deps (run manually before releases)
- `npm audit` on frontend deps
- GitHub Dependabot alerts (when enabled by the repo owner)

Critical CVEs in direct dependencies (FastAPI, Temporal, LangGraph,
PydanticAI, Next.js, Postgres driver) are patched in the next patch
release after disclosure.
