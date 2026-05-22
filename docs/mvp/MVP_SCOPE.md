# MVP Scope

The MVP should prove that Helix Migration can run as a self-hosted enterprise migration command center with core admin, project, metadata, agent planning, validation, and reconciliation workflows.

## Included

- Docker Compose installation
- Frontend application shell
- FastAPI backend shell
- PostgreSQL metadata store
- Redis integration
- Temporal integration
- First admin setup
- Authentication foundation
- Organization management foundation
- User and role foundation
- LLM provider configuration
- API key encryption and masking
- Agent-wise model mapping
- Project and subproject creation
- Requirement intake
- BMAD planning workflow
- Typed agent outputs
- Human approval step
- Source and target metadata entry or upload
- Schema, table, and column metadata storage
- Basic schema comparison
- Validation rule planning
- Row count validation
- Null and duplicate check definitions
- Basic reconciliation report
- Audit logs for key actions

## Excluded

- Full production data movement
- Full customer data storage by default
- Advanced connector catalog
- SSO and LDAP/AD
- Helm chart
- Advanced lineage engine
- Full dbt orchestration
- Full Great Expectations suite authoring UI
- Complex scheduling system
- Multi-region deployment
- Billing or commercial license features

## Developer Execution MVP Scope

Included in MVP:

- Upload `.py` and `.sql` files
- Store artifact metadata
- Analyze uploaded code
- Generate AI explanation
- Generate code review summary
- Generate draft converted code or Databricks notebook structure
- Show side-by-side diff
- Save versioned artifact
- Track human approval status

Excluded from MVP:

- Full automated production migration
- Complex multi-file project conversion
- Automatic deployment of generated code
- Full Git integration
- Full notebook execution runtime
- All ETL tools support

Scope statement:

```text
Helix Migration generates draft migration code, notebook structures, validation plans, and reconciliation reports that must be reviewed and approved by humans before production use.
```

## MVP User Journeys

### First Admin Journey

1. Start Helix Migration with Docker Compose.
2. Open the frontend.
3. Create first admin account.
4. Create organization.
5. Configure default LLM provider.
6. Verify provider connection.

### Project Workflow

1. Create migration project.
2. Add subproject.
3. Enter migration requirement.
4. Add source and target metadata.
5. Run agent planning workflow.
6. Review generated outputs.
7. Approve architecture plan.
8. Generate validation and recon plan.
9. Export report.

### MVP Agent Workflow

```text
Requirement
  -> Business Analyst Agent
  -> Architect Agent
  -> Human Approval
  -> Data Engineer Agent
  -> QA / Validation Agent
  -> Recon Agent
  -> DevOps Agent
  -> PM Agent
  -> Final Review
```

## MVP Admin Journey

Admin should be able to:

- Invite or create users
- Assign roles
- Configure LLM providers
- Rotate API keys
- Configure default model
- Configure agent-wise model mapping
- View audit logs
- View system health

## MVP Success Criteria

- New user can run the platform through Docker Compose.
- First admin can configure organization and LLM provider.
- User can create a project and requirement.
- Agent workflow produces typed outputs.
- Human approval is required before execution-oriented agent steps.
- PostgreSQL stores metadata, outputs, approvals, and audit logs.
- API keys are encrypted and masked.
- Validation and recon summaries can be generated from metadata.
- Developer can upload a `.py` or `.sql` artifact, receive AI analysis, view draft generated output, compare a diff, save a version, and set approval status.
- Documentation is clear enough for contributors to continue implementation.

## Final MVP Boundary

MVP included:

- Admin login
- LLM key setup
- User/project management
- Requirement intake
- BMAD planning workflow
- Basic developer workspace
- Upload `.py` and `.sql` files
- Analyze uploaded code
- Generate code review summary
- Generate draft converted code/notebook structure
- Store artifact metadata
- Basic artifact versioning
- Basic validation/recon report generation
- Basic audit logs
- Basic system health page
- Docker Compose installation
- Templates as static JSON/YAML files
- Safe code analysis only, not arbitrary code execution

MVP excluded:

- Full marketplace
- Full vector DB memory
- Full Git integration
- Full automatic code migration
- Direct code execution
- Full notebook runtime
- All connectors
- Full Kubernetes support
- Production deployment automation

MVP must keep PostgreSQL as the metadata store, artifact files outside PostgreSQL, encrypted/masked LLM keys, and human approval before production use of generated artifacts.
