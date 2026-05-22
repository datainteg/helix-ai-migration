# Backup and Restore

## Scope

Back up PostgreSQL metadata and artifact storage together. PostgreSQL stores metadata only. Uploaded/generated files live in local filesystem storage for MVP and MinIO/S3-compatible storage later.

## MVP Backup

- Use `pg_dump` for PostgreSQL metadata.
- Archive `data/artifacts/` at the same logical backup point.
- Store backup timestamp and application version.
- Verify backup integrity by restoring into a separate environment.

## Restore

1. Stop application workers.
2. Restore PostgreSQL.
3. Restore artifact storage.
4. Verify artifact paths and content hashes.
5. Start backend and workers.
6. Run health checks.

## Future Production

Future deployments may use WAL archiving, point-in-time recovery, managed PostgreSQL backups, and MinIO/S3 lifecycle policies.

