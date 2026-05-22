# Import and Export

## Export Formats

Planned formats:

- PDF
- Markdown
- JSON
- CSV
- HTML

## Export Types

- Project config export
- Migration plan export
- Validation report export
- Recon report export
- Agent outputs export
- Templates export
- Artifact metadata export

## Import Types

- Project configuration import
- Template import
- Validation rule import
- Metadata import

Imports should validate schema, organization scope, and security boundaries before creating records.

## Import Validation Rules

All imports must pass validation before records are created:

| Rule | Description |
|---|---|
| Schema validation | Imported JSON/YAML/CSV must conform to the expected schema for the import type. Reject malformed payloads with clear field-level errors. |
| Organization scoping | Imported records must be scoped to the requesting user's organization. Cross-organization references are rejected. |
| Duplicate detection | Detect duplicate project names, template names, and validation rule identifiers within the same organization. Offer skip or overwrite options where safe. |
| Size limits | Maximum import payload: 10 MB for JSON/YAML, 25 MB for CSV. Larger files should use artifact upload instead. |
| Reference integrity | Imported records referencing non-existent entities (e.g., a validation rule referencing a missing project) must fail with a descriptive error. |
| Partial success | Imports should be transactional: all-or-nothing for a single import batch. Do not create partial records on failure. |
| Audit logging | Every import attempt (success or failure) must create an audit log entry with actor, import type, record count, and result. |
| Rate limiting | Import endpoints share the standard authenticated-user rate limits. |
| Secret handling | Imports must not contain plaintext secrets. If a template or config references secrets, they must be configured separately through the secrets management system. |

## Import Error Response Format

```json
{
  "error": {
    "code": "IMPORT_VALIDATION_ERROR",
    "message": "Import validation failed",
    "details": [
      {
        "row": 12,
        "field": "project_name",
        "message": "Project name already exists in organization"
      }
    ],
    "import_id": "imp_abc123",
    "records_attempted": 50,
    "records_failed": 1
  }
}
```

