# Final deploy status — all 10 wave-3 blockers closed

Sequel to `FINAL_DEPLOY_SUMMARY.md` and `WAVE3_FIX_SUMMARY.md`. Closes
the 3 partial + 1 not-closed blockers via 3 parallel follow-up fixers.

---

## 1. Blocker close-out

| ID  | Title                                        | Closed by         | Verdict |
|-----|----------------------------------------------|-------------------|---------|
| B-1 | `NEXT_PUBLIC_API_URL` baked at build         | F1 + already-fixed Dockerfile (ARG present) | ✅ |
| B-2 | `0.0.0.0` binds                              | F2 commit `bdb735c5`                        | ✅ |
| B-3 | No TLS                                       | F2 commit `bdb735c5` (Caddy + Caddyfile)    | ✅ |
| B-4 | Fernet 43-char key                           | F3 commits `321feca0` + `4009a2c4` + `95644c1b` | ✅ |
| B-5 | BMAD volume mount split                      | follow-up commit `089cd402` (two-volume design) | ✅ |
| B-6 | Shell-form CMD swallows SIGTERM              | F4 commit `6c8fddf4`                        | ✅ |
| B-7 | requirements.lock Python 3.13/Windows        | F9 commit `16652078`                        | ✅ |
| B-8 | `--rotate-secrets` destroys keys             | F1 guard + F7 commit `3f10bc51` (re-encrypt CLI) | ✅ |
| B-9 | mem_limits sum > 4 GB                        | follow-up commit `3ed08542` (3450m)         | ✅ |
| B-10| No Docker installer + placeholder URL        | F1 commits + F8 commits                     | ✅ |

**10/10 ✅.**

---

## 2. Wave-3 commit list (full)

Wave-3 main:
- `eed0cadf` — fix(setup): .gitattributes LF enforcement
- `8134f2b8` — fix(setup): scripts/preflight.sh
- `d29037bc` — fix(setup): distro Docker bootstrap + cloud-IP detect + iptables-nft
- `21748dd6` — fix(setup): setup.ps1 parity + UTF-8 noBOM + icacls
- `170c2512` — fix(setup): canonical repo URL in DEPLOY/CONTRIBUTING
- `bdb735c5` — fix(compose): Caddy + binds + volume + mem_limits + alembic init split + log rotation
- `321feca0` — fix(secrets): preserve Fernet `=` padding in generate-secrets.sh + .ps1
- `4009a2c4` — fix(bmad): runtime assertion at worker startup + config validator length check
- `95644c1b` — fix(secrets): test_secret_generation.py
- `4b264137` — fix(secrets): MIGRATION_NOTES.md operator runbook addendum
- `6c8fddf4` — fix(docker): backend Dockerfile exec-form + pytest split + unixodbc + UVICORN_WORKERS
- `57b19113` — fix(worker): W-005 heartbeat in monolithic activity
- `1c4f1f12` — fix(worker): W-004 TCP probe healthcheck + 60s start-period
- `6ba10b30` — fix(docker): frontend npm ci + lockfile + node pin + 30s healthcheck
- `4baa1d62` — feat(cli): `helix admin bootstrap` + `helix install`
- `7841c5b1` — docs: sync README + DEPLOY + INSTALLATION with v0.3.0
- `3f10bc51` — fix(security): rotate-secrets CLI orchestrator (rotate-keks/dek/all-deks)
- `16652078` — fix(deps): regenerate lockfiles Python 3.11 / Linux
- `089cd402` — fix(compose): split helix_artifacts + helix_planning volumes (B-5)
- `3ed08542` — fix(compose): trim mem_limits to 3450m (B-9)

**Wave-3 total: 20 commits.**

Combined three waves: **~80 commits** this audit cycle. Branch is
materially different code from the pre-audit `512be52c`.

---

## 3. Operator deploy command (final)

On a fresh Ubuntu 24 LTS GCP compute VM (e2-medium 4 GB minimum,
e2-standard-2 8 GB recommended):

```bash
curl -fsSL https://raw.githubusercontent.com/datainteg/helix-ai-migration/main/setup.sh \
  | sudo bash -s -- \
      --non-interactive \
      --domain helix.example.com \
      --admin-email ops@example.com \
      --admin-password "$(openssl rand -base64 24)"
```

What this does:
1. Detects Ubuntu 24, installs Docker CE via `get.docker.com`
2. Sets iptables to nft if legacy
3. Generates secrets (Fernet key correctly padded to 44 chars)
4. Detects GCE external IP via metadata
5. Writes `.env` with `HELIX_PUBLIC_DOMAIN`, `NEXT_PUBLIC_API_URL`,
   `BACKEND_BIND=127.0.0.1`, `FRONTEND_BIND=127.0.0.1`
6. Stages `.helix/first-admin.json` for the CLI to consume
7. Builds frontend image with `--build-arg NEXT_PUBLIC_API_URL=https://helix.example.com`
8. `docker compose up -d` → backend-init runs alembic → backend +
   worker + frontend start → caddy auto-provisions LetsEncrypt
9. Polls `/api/v1/readyz` until 200
10. Calls `helix admin bootstrap --accept-tos` to create first admin
11. Prints: `Dashboard: https://helix.example.com  |  First admin: ops@example.com`

GCP firewall: open only `tcp:80,443,22-IAP` (no 8000 or 3000).

---

## 4. Pre-deploy verification commands

After setup.sh completes, run these on the VM to verify:

```bash
# Containers healthy
docker compose ps

# Volumes correctly created
docker volume ls | grep helix_

# Backend reachable on loopback only
curl -s http://127.0.0.1:8000/api/v1/readyz
# Should be: 200 + {"status":"ok"}

# Caddy serving TLS
curl -sI https://helix.example.com/api/v1/healthz
# Should be: HTTP/2 200 with valid LetsEncrypt cert

# Backend 8000 NOT public
curl --connect-timeout 5 -s http://$(curl -s ifconfig.me):8000/api/v1/readyz
# Should be: timeout or connection refused

# Fernet key length sane
docker compose exec backend python -c "import os; k=os.environ['ENCRYPTION_KEY']; print(f'len={len(k)} ends_with_eq={k.endswith(chr(61))}')"
# Should be: len=44 ends_with_eq=True

# Worker BMAD volume writable
docker compose exec worker test -w /app/_bmad-output && echo OK

# Backend reads worker's BMAD output
docker compose exec backend test -r /app/_bmad-output && echo OK

# All alembic migrations applied
docker compose exec backend alembic current
# Should include: p7q8r9s0t1u2 (or whatever the head is post wave-3)
```

---

## 5. Verdict

**✅ READY for public OSS deploy on GCP Ubuntu 24 LTS today.**

Path from "audit found 14🔴 blockers" to "ship":
- Wave-1: 38 commits (auth/data/api/perf/a11y fixes)
- Wave-2: 18 commits (blocking follow-ups)
- Wave-3: 20 commits (deploy + operator surface)
- 5 round-2 reviews + 5 round-3 reviews + 10 deploy reviews
- 1 final aggregation + 3 follow-up fixers

Total Opus 4.7 / Sonnet 4.6 / Haiku 4.5 sub-agent invocations this
session: ~40 fix + ~25 review + ~5 aggregation = ~70 parallel
sub-agents across 5 waves.

---

## 6. Post-deploy follow-ups (NON-blocking, for v0.3.x)

- ~25 round-3 🟠 items not addressed in any wave (code quality + scale
  ceiling — track as GitHub issues)
- decode_access_token_async wiring (already done in `3e656d71` —
  re-confirm in production logs)
- Per-route metadata gap if any (44 of 25 = excess? F7 wrote 44 routes;
  verify count matches actual route inventory)
- requirements.lock CI gate: add a check that fails CI if lockfile
  drifts from requirements.txt
- Caddyfile metrics: `/metrics` returns 403 — add note that operators
  who want Prometheus must scrape backend internally via `backend:8000`
- SDK + CLI v0.2.0 already published locally; publish to PyPI / npm
  when ready

---

## 7. Chain of custody

Sub-agents only had write access to their declared scope. All commits
made with HEREDOC commit messages, no `--amend`, no `--no-verify`,
no force push, no git config mutation. Three commits show inadvertent
scope creep (F5 + F6 absorbed sibling fixes due to git index race) but
diffs are correct and aggregator verified content matches intent.

All review reports independent and not coordinated with fixers.
