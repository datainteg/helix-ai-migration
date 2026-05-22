# Secrets Management

## MVP Secrets Model

MVP should store secrets encrypted in PostgreSQL using backend-managed encryption. Full API keys must never be returned after save. UI and API responses should show masked values only.

Secrets include:

- LLM provider API keys
- Custom model API keys
- Connector credentials
- JWT secrets
- Encryption keys

## Rotation and Masking

Track secret version, created timestamp, rotated timestamp, actor, and audit log ID. Mask keys in all read responses.

## Future External Secret Managers

Planned support:

- Docker secrets
- HashiCorp Vault
- AWS Secrets Manager
- Azure Key Vault
- GCP Secret Manager

External secret references should be stored in PostgreSQL without copying secret values into metadata tables.

