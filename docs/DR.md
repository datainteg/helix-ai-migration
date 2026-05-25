# Disaster Recovery — Helix Migration

Two artifacts every Helix deployment must protect:

1. **`helix_postgres_data` volume** — every project, workflow, audit chain entry, encrypted LLM key.
2. **`helix_artifacts` volume** — BMAD-generated markdown + uploaded code artifacts.

Lose either and the platform is unusable. Lose Postgres alone and even a fresh frontend boot cannot recover user state.

---

## Backup

### Manual

```bash
./scripts/backup.sh
```

Produces:

```
backups/<UTC-stamp>/
├── postgres.sql.gz       pg_dump --clean --if-exists, gzipped
├── artifacts.tar.gz      tar of the helix_artifacts volume
└── MANIFEST.txt          sha256 of both files + host metadata
```

### Optional S3 / S3-compatible upload

Set `HELIX_BACKUP_S3_BUCKET` (and optionally `HELIX_BACKUP_S3_PREFIX`) in `.env`. The script uploads the whole stamp folder with `aws s3 cp --recursive` after the local files are written. AWS credentials come from the standard chain (env vars, IAM instance role, `~/.aws/credentials`).

### Scheduled (cron)

```cron
# Daily 03:00 UTC. Stdout/stderr go to /var/log/helix-backup.log.
0 3 * * * /opt/helix/scripts/backup.sh >> /var/log/helix-backup.log 2>&1
# Prune empty backup folders older than 30 days.
30 3 * * * find /opt/helix/backups -mtime +30 -type d -empty -delete
```

For systemd timers, write a `helix-backup.service` + `helix-backup.timer`. Sample unit lives in `docs/systemd/`.

---

## Restore

```bash
./scripts/restore.sh backups/20260525-031500
# or:
./scripts/restore.sh s3://my-bucket/helix-backups/20260525-031500
```

The script:

1. Stages the backup locally (downloads from S3 if needed).
2. Stops `backend` + `worker` so no writers race.
3. Runs `gunzip … | psql` to replay the Postgres dump.
4. Wipes the artifact volume + extracts the tarball.
5. Restarts `backend` + `worker`.

Requires `restore` typed at the confirmation prompt. After the script completes, hit `/api/v1/audit-logs/verify` to confirm the audit chain HMAC still validates — if it does, your restore was bit-for-bit successful.

---

## Verify your DR strategy

Restoring once is not "having backups". Every quarter:

1. Take a fresh `./scripts/backup.sh` on the primary.
2. Stand up a sacrificial host (compose, no traffic).
3. Run `./scripts/restore.sh` against that host with the backup.
4. Walk through the operator flow: login, create a project, view audit logs, run `audit-logs/verify`.
5. Tear the sacrificial host down.

Record the drill in `docs/dr-drills.md`.

---

## RPO / RTO targets

| Metric | Target | How to achieve |
|---|---|---|
| RPO (data loss tolerance) | ≤ 24 hours | Daily cron backup; tighten to hourly for high-write orgs via WAL archiving (`pg_basebackup` + `archive_command`). |
| RTO (recovery time) | ≤ 30 minutes | Restore script + S3 staging completes in 5-10 min for <5 GB DB. Practice quarterly. |

For tighter RPO add streaming Postgres replication to a hot-standby — covered in a follow-up runbook.
