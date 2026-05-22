# Testing Strategy

## Test Pyramid

- Unit tests for services, schemas, validation rules, and helper functions
- API tests for FastAPI routers and RBAC boundaries
- Integration tests with PostgreSQL, Redis, and Temporal test workers
- Frontend component tests for forms, navigation, diff views, and empty/error/loading states
- End-to-end smoke tests for Docker Compose once implementation exists

## Agent Testing

- Use deterministic mock LLM providers.
- Validate every PydanticAI structured output schema.
- Test invalid model output and schema repair paths.
- Record prompt version and model metadata in test fixtures.

## Security Tests

- API keys are encrypted before storage.
- API keys and SMTP secrets are masked in responses.
- Cross-organization access is denied.
- Uploaded code is not executed in MVP.
- Artifact files are stored outside PostgreSQL.

## Artifact Test Fixtures

Use small `.py` and `.sql` fixtures for upload, hash generation, code review, conversion metadata, and side-by-side diff tests.

