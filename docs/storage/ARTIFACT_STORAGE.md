# Artifact Storage

## Purpose

Artifact storage stores uploaded and generated files while PostgreSQL stores metadata.

## MVP Storage

MVP should use local filesystem storage:

```text
data/artifacts/
```

Examples:

- Uploaded `.py`, `.sql`, `.ipynb` files
- Generated notebooks
- Generated code files
- Recon reports
- Validation exports
- Mapping files
- Documentation exports

## PostgreSQL Metadata

PostgreSQL stores:

- Artifact path
- Content hash
- Version
- Owner
- Approval status
- Storage provider
- Metadata
- Audit trail

PostgreSQL should not store file contents by default.

## Future Storage

Future storage should support MinIO/S3-compatible providers through a storage abstraction.

## Versioning and Retention

Each artifact version should have a content hash, created timestamp, creator, approval status, and lineage links. Retention should be configurable per organization.

