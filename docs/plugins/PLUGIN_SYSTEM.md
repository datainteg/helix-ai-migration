# Plugin System

## Goals

The plugin system should eventually allow Helix Migration to be extended without changing core platform code.

Plugin types:

- Custom connectors
- Custom validation rules
- Custom agents
- Custom templates
- Custom report formats
- Custom LLM providers

## Security Boundaries

Plugins must be explicitly installed and enabled. Plugin actions should be audited. Plugins must respect organization boundaries, RBAC, secret handling, artifact access controls, and safe execution rules.

## MVP Scope

MVP should not build a full marketplace. MVP may define plugin concepts and leave extension points for future implementation.

## Future Marketplace

Future marketplace support may include plugin discovery, versioning, compatibility checks, signed packages, install controls, and admin approval.

