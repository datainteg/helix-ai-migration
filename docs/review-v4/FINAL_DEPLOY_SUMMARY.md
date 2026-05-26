# Final deployment-readiness summary

10 parallel sub-agents (2× Opus, 7× Sonnet, 1× Haiku) auditing every
surface a fresh Ubuntu 24 LTS GCP compute VM operator would touch.
Plus 1 aggregator (which finalized at 7/10 due to polling timing —
this file aggregates all 10).

Source reports (this directory):
- [DEPLOY_SETUP.md](DEPLOY_SETUP.md) — setup.sh + setup.ps1 portability
- [DEPLOY_COMPOSE.md](DEPLOY_COMPOSE.md) — docker-compose v1/dev/build
- [DEPLOY_BACKEND_IMAGE.md](DEPLOY_BACKEND_IMAGE.md)
- [DEPLOY_WORKER_IMAGE.md](DEPLOY_WORKER_IMAGE.md)
- [DEPLOY_FRONTEND_IMAGE.md](DEPLOY_FRONTEND_IMAGE.md)
- [DEPLOY_SECRETS.md](DEPLOY_SECRETS.md) — `.env.example` + secret generation
- [DEPLOY_UBUNTU24.md](DEPLOY_UBUNTU24.md)
- [DEPLOY_GCP_NETWORK.md](DEPLOY_GCP_NETWORK.md)
- [DEPLOY_FIRST_RUN.md](DEPLOY_FIRST_RUN.md) — operator E2E walkthrough
- [DEPLOY_DOCS.md](DEPLOY_DOCS.md) — README + DEPLOY.md drift

---

## 1. Aggregate counts

| Area                | 🔴 | 🟠 | 🟡 | 🔵 | Total |
|---------------------|---:|---:|---:|---:|------:|
| setup.sh portability |  4 |  9 | 11 |  6 |    30 |
| docker-compose       |  1 | 10 | 10 |  4 |    25 |
| backend Dockerfile   |  2 |  6 |  7 |  4 |    19 |
| worker Dockerfile    |  2 |  4 |  5 |  4 |    15 |
| frontend Dockerfile  |  1 |  2 |  4 |  4 |    11 |
| secrets / .env       |  2 |  6 |  5 |  4 |    17 |
| Ubuntu 24 compat     |  0 |  1 |  3 |  6 |    10 |
| GCP network          |  3 |  7 |  6 |  4 |    20 |
| first-run E2E        |  3 hard stops, not severity-tagged |
| doc sync             |  3 stale docs of 7 |
| **TOTAL**            | **15** | **45** | **51** | **36** | **~150** |

Genuine launch-blockers: **15 🔴** (some overlap across reports — actual
unique blockers ≈ 10).

---

## 2. Top 10 unique launch-blockers (de-duplicated across reports)

Ranked by deploy impact + likelihood every first-run operator hits it.

### B-1 🔴 `NEXT_PUBLIC_API_URL` baked at build time, defaults to localhost
- **Flagged by:** GCP-network (GCP-004), Frontend image (FE-002), Compose (DC-011), Secrets (DS-007), First-run (STOP-2)
- **Symptom:** Every GCP-VM operator opens dashboard → "Failed to fetch"
- **Fix:** setup.sh auto-detects GCE external IP via metadata; passes as `--build-arg` to `docker compose build`; document the rebuild step

### B-2 🔴 `0.0.0.0` port bindings + DEPLOY.md tells operator to `ufw allow 8000/tcp`
- **Flagged by:** GCP-network (GCP-001, GCP-002), setup.sh (DSETUP-028), Compose (DC-013)
- **Symptom:** Backend FastAPI + admin endpoints + `/metrics` + OpenAPI docs publicly exposed on VM external IP
- **Fix:** `BACKEND_BIND=127.0.0.1` default; add Caddy reverse proxy service to compose; remove `ufw allow 8000` from DEPLOY.md

### B-3 🔴 No TLS anywhere
- **Flagged by:** GCP-network (GCP-005)
- **Symptom:** Bearer tokens, secrets, BMAD prompts travel plaintext
- **Fix:** Caddyfile + caddy compose service (auto-LetsEncrypt). Snippet in DEPLOY_GCP_NETWORK.md

### B-4 🔴 Fernet key generation broken on Windows + on Ubuntu 24 without `python3-cryptography`
- **Flagged by:** Secrets (DS-001, DS-002), setup.sh (DSETUP-011)
- **Symptom:** PowerShell emits 43-char Fernet key (must be 44); shell fallback strips `=` padding. Config validator masks the bug by adding `==` before decode. First `encrypt_value()` crashes.
- **Fix:** preserve the `=` pad in fallback; `config.py` rejects `len(key) != 44` BEFORE base64 decode

### B-5 🔴 Worker BMAD artifacts written to ephemeral container layer
- **Flagged by:** Worker image (W-002)
- **Symptom:** `_bmad-output/` resolves to `/app/_bmad-output` (ephemeral); compose volume mounts at `/app/data/artifacts`. Every artifact lost on restart.
- **Fix:** point `_bmad/bmm/config.yaml:7` planning_artifacts root to `/app/data/artifacts/_bmad-output` OR mount volume at `/app/_bmad-output`

### B-6 🔴 Backend Dockerfile shell-form CMD swallows SIGTERM
- **Flagged by:** Backend image (INFRA-014)
- **Symptom:** `docker stop` is hard SIGKILL after 10s; in-flight requests dropped
- **Fix:** `ENTRYPOINT ["sh","-c","alembic upgrade head && exec uvicorn ..."]` — note the `exec` so PID 1 becomes uvicorn

### B-7 🔴 Worker lockfile generated on Python 3.13/Windows, runner is Python 3.11/Linux
- **Flagged by:** Worker image (W-001), Backend image (cross-flagged)
- **Symptom:** ABI-tagged wheels mismatch; `google-cloud-aiplatform` dropped from lockfile; Vertex AI silently broken
- **Fix:** regenerate via `scripts/lock-requirements.sh` on a Linux Python 3.11 container

### B-8 🔴 `setup.sh --rotate-secrets` silently destroys `ENCRYPTION_KEY` + `AUDIT_HMAC_KEY`
- **Flagged by:** setup.sh (DSETUP-010, INFRA-020), Secrets (DS-003)
- **Symptom:** Operator follows "rotate every 90 days" runbook → every stored LLM credential decrypts to `InvalidToken`; audit chain HMAC broken
- **Fix:** `--rotate-secrets` should require `--force` + explicit re-encryption pass (wave-1 added `rotate_kek_secrets`; wire it in)

### B-9 🔴 Compose `mem_limit` sum exceeds 4 GB on e2-medium target
- **Flagged by:** Compose (DC-015)
- **Symptom:** Declared limits sum to 4864 MB on a 4 GB VM → OOM-killer eats services
- **Fix:** rebalance to ≤ 3712 MB OR recommend e2-standard-2 (8 GB) as minimum

### B-10 🔴 No Docker installer; placeholder repo URL; first-admin UI-only
- **Flagged by:** setup.sh (DSETUP-001, DSETUP-031), First-run (STOP-1, STOP-3)
- **Symptom:** On a fresh Ubuntu 24 VM, `setup.sh` aborts (Docker missing); README has `<your-fork>` placeholder; no headless `helix admin bootstrap` CLI
- **Fix:** setup.sh detects + installs Docker CE via `get.docker.com` (Ubuntu/Debian/Fedora/RHEL); pin canonical repo URL in README; add `helix admin bootstrap --email --password` CLI command

---

## 3. High-impact 🟠 themes (group-fixable)

1. **alembic on every restart** — backend Dockerfile runs `alembic upgrade head` on boot. Race on scale-out. Fix: separate `init-migrate` one-shot service in compose.
2. **No log rotation** — Docker default `json-file` no max-size. GCP VM disk fills.
3. **frontend `npm install --legacy-peer-deps` without lockfile** — non-deterministic builds; CVE scan invalid.
4. **Healthchecks too aggressive** — Temporal `|| true` always passes; worker 30s start_period too short for cold dep import; frontend 15s too short.
5. **CRLF hazards** — no `.gitattributes`; Windows clones break setup.sh.
6. **No `--non-interactive` flag** — setup.sh prompts → curl|bash fails.
7. **Dev overlay leak** — passing `-f docker-compose.dev.yml` disables prod security guards.
8. **TEMPORAL_UI default `admin/admin`** — INFRA-039 confirmed still default-shipped.
9. **CORS_ORIGINS still `localhost`** — fails prod validator silently because no `*`, but rejects all real browsers.
10. **Doc drift** — README missing SDK v0.2.0 + CLI + envelope + new endpoints; INSTALLATION.md wrong ports.

---

## 4. Recommended one-command install (after blockers closed)

```bash
# On a fresh Ubuntu 24 LTS GCP VM (e2-standard-2 minimum, 8 GB RAM, 50 GB disk)
curl -fsSL https://raw.githubusercontent.com/datainteg/helix-ai-migration/main/setup.sh \
  | sudo bash -s -- \
      --non-interactive \
      --domain helix.example.com \
      --admin-email ops@example.com \
      --auto-detect-ip
```

The script (post-fixes) must:
1. Install Docker CE via `get.docker.com`
2. Set iptables backend to nft if needed
3. Generate secrets with proper Fernet padding
4. Autodetect GCE external IP via metadata service
5. Write `.env` with detected `NEXT_PUBLIC_API_URL`
6. Build frontend image with `--build-arg NEXT_PUBLIC_API_URL=$(IP)`
7. Bring up the stack: `docker compose up -d`
8. Run alembic upgrade head in a one-shot init container
9. Wait for `/readyz` to return 200
10. Print: "Dashboard: https://helix.example.com  |  First admin: visit /setup/first-admin"

---

## 5. Pre-deploy checklist (10 items)

- [ ] B-1 fixed: `NEXT_PUBLIC_API_URL` auto-detection + build-arg path
- [ ] B-2 fixed: `BACKEND_BIND=127.0.0.1` default; ufw doc updated
- [ ] B-3 added: Caddy compose service + Caddyfile committed
- [ ] B-4 fixed: Fernet padding preserved in both `.sh` and `.ps1`; validator length check
- [ ] B-5 fixed: BMAD artifact dir mounted at correct path
- [ ] B-6 fixed: exec-form CMD in backend Dockerfile
- [ ] B-7 fixed: worker + backend `requirements.lock` regenerated on Linux/3.11
- [ ] B-8 fixed: `--rotate-secrets` guarded behind `--force` + re-encryption
- [ ] B-9 fixed: mem_limits ≤ 3712 MB OR doc minimum bumped to 8 GB
- [ ] B-10 fixed: Docker installer + canonical repo URL + headless admin bootstrap

---

## 6. Verdict

**❌ NOT ready for same-day GCP production deploy as a 1-click product.**

- 10 unique launch-blockers across surfaces
- ~2 engineering-days of focused fixes
- Many already partially in-flight (wave-1 + wave-2 closed the AUTH /
  data / a11y / API layers — but the *operator surface* remains the
  weakest layer)

**Path to ✅:**
- Wave-3 fix sprint focused exclusively on the 10 blockers above
- Single VM smoke test on a fresh Ubuntu 24 e2-standard-2 (8 GB)
- Documentation pass to align README + DEPLOY.md + INSTALLATION.md
- Tag `v0.3.0` and announce

**Realistic same-day deploy IS possible if scoped narrowly:**
- Deploy for YOUR team (you on the VM, no public IP) → ship today, the
  app-layer fixes already landed are sufficient
- One-click public OSS announcement → wait 2 days, close the 10
  blockers above

---

## 7. Chain-of-custody

- 10 review agents + 1 aggregator, all Opus 4.7 / Sonnet 4.6 / Haiku 4.5
- No agent had write access to source code; only this directory
- Aggregator's `DEPLOY_SUMMARY.md` was written at 7/10 due to polling
  race; this `FINAL_DEPLOY_SUMMARY.md` aggregates all 10 actual reports
- Counts reproduce per-report tables verbatim where reports tabulated;
  estimated where prose-only
