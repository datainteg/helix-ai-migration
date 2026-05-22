# Feature Breakdown

## Epic 1: Foundation

Goal: Create a clean, runnable open-source platform base.

- Monorepo structure
- Docker Compose services
- Frontend shell
- Backend shell
- Worker shell
- Environment configuration
- Health endpoints

## Epic 2: Auth/Admin

Goal: Provide secure first-use administration.

- First admin setup
- Login/logout/current user
- Organization setup
- Users and roles
- RBAC foundation
- Admin navigation

## Epic 3: LLM Provider Settings

Goal: Support bring-your-own-key AI configuration.

- Provider list/create/update/delete
- Encrypted API key storage
- Masked key display
- Key rotation
- Test connection
- Agent-wise model mapping
- LLM usage audit hooks

## Epic 4: Project Workspace

Goal: Create the core migration management workspace.

- Project list
- Create project
- Subprojects
- Requirement intake
- Source/target metadata
- Schema/table/column metadata
- Project activity and approvals

## Epic 5: Agent Runtime

Goal: Run typed, reviewable migration planning agents.

- Agent definitions
- Prompt templates and versions
- BMAD workflow
- LangGraph orchestration
- Temporal durable workflow wrapper
- PydanticAI structured outputs
- Agent output storage
- Human approval gate

## Epic 6: Developer Workspace

Goal: Provide safe developer execution support without running uploaded code.

- Artifact upload for `.py` and `.sql`
- Artifact metadata and content hashes
- Code Analyzer Agent output
- Code Review Agent output
- Draft conversion run metadata
- Side-by-side diff viewer
- Artifact version history
- Human approval workflow

## Epic 7: Validation/Reconciliation

Goal: Generate practical migration quality outputs from metadata.

- Validation rule planning
- Row count checks
- Null and duplicate check definitions
- Schema comparison
- Recon summary
- Report metadata
- Export-ready report records

## Epic 8: Governance/Audit

Goal: Make security-sensitive actions visible and reviewable.

- Login/admin audit events
- LLM provider changes
- Key rotation events
- Agent workflow events
- Artifact upload/review/approval events
- Report export events

## Epic 9: Observability

Goal: Provide basic operational visibility.

- Backend health
- Database connectivity
- Redis status
- Temporal status
- Worker status
- Failed jobs summary
- LLM latency/token metrics foundation

## Epic 10: Docker/Open-Source Release

Goal: Make the project easy to run and contribute to.

- Docker Compose validation
- `.env.example`
- README install flow
- Release checklist
- Screenshots
- License
- Contribution notes
- Docker images:
  - `datainteg/helix-ai-migration-frontend`
  - `datainteg/helix-ai-migration-backend`
  - `datainteg/helix-ai-migration-worker`
