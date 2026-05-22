# Prompt Engineering

## Purpose

Prompt engineering in Helix Migration must produce typed, auditable, schema-valid outputs. Free-form unstructured agent responses are not acceptable for persisted workflow artifacts.

## Prompt Template Structure

Prompts should define:

- Agent role
- Project context
- Input metadata
- Constraints
- Required output schema
- Safety rules
- Assumptions and limitation handling
- Human approval reminder for generated artifacts

## Evaluation

Prompt changes should be tested with:

- Mock LLM provider
- Schema validation
- Golden sample inputs
- Failure case inputs
- Regression checks for assumptions, risks, and required fields

## Versioning

Every prompt execution should reference prompt template ID, prompt version, agent type, provider, model, token usage, latency, and output schema version.

