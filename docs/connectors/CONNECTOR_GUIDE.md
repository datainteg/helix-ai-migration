# Connector Guide

Helix Migration connectors extract metadata from source and target systems. They should support validation and reconciliation without storing full production business data by default.

## Connector Responsibilities

- Test connection
- Extract metadata
- Scan schemas
- List tables and columns
- Capture row counts
- Capture basic profiles when allowed
- Provide references for validation and recon

## Connector Interface

Expected connector operations:

```text
test_connection()
list_schemas()
list_tables(schema)
list_columns(schema, table)
get_row_count(schema, table)
get_table_profile(schema, table)
scan_schema()
```

Implementation should define a typed base interface during coding.

## Metadata Extraction

Metadata should include:

- Connection type
- Database or catalog name
- Schema name
- Table name
- Column name
- Data type
- Nullability
- Primary key markers when available
- Row count when available
- Snapshot timestamp

## Test Connection

Test connection should:

- Validate credentials.
- Validate network access.
- Avoid expensive queries.
- Return safe error messages.
- Write audit logs.
- Never expose secrets.

## Schema Scan

Schema scan should:

- Create a schema snapshot.
- Store schemas, tables, and columns.
- Store row counts when configured.
- Detect metadata changes across snapshots.
- Avoid storing full data rows by default.

## Row Count

Row count checks should be:

- Optional per table.
- Timeout-limited.
- Stored as metadata.
- Used by validation and recon summaries.

## Supported Connector Roadmap

Planned connectors:

- PostgreSQL
- MySQL
- SQL Server
- Oracle
- Snowflake
- Databricks
- MongoDB
- S3
- Files: CSV, JSON, Parquet
- APIs
- ETL systems

## Add a New Connector

Steps:

1. Add connector package under `connectors/`.
2. Implement base connector interface.
3. Add typed configuration schema.
4. Add secret handling through encrypted storage.
5. Add test connection.
6. Add schema scan.
7. Add row count support if possible.
8. Add unit tests.
9. Add documentation and examples.

## Security Rules

- Store credentials encrypted.
- Mask connection secrets.
- Do not log credentials.
- Do not store business data by default.
- Audit test connection and scan actions.
- Respect organization and project scope.

## Connector Extension Layer

Connectors should become plugin-based over time. MVP should keep connector work metadata-only and limited.

Plugin-based connector roadmap:

- Custom connector packages
- Connector templates
- Connector health checks
- Credential testing
- Metadata extraction
- Schema scan
- Row count summaries
- Validation template mapping

Connector interface as future extension layer:

- `test_connection`
- `discover_metadata`
- `scan_schema`
- `get_row_count`
- `get_health`
- `get_supported_templates`

Safe credential handling:

- Store credentials encrypted or by external secret reference.
- Mask credential values.
- Never log credentials.
- Audit test and scan actions.
- Keep connector results scoped to organization and project.
