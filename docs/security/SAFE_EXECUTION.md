# Safe Execution

## MVP Rule

MVP must not execute arbitrary uploaded code. Uploaded code is untrusted input.

MVP behavior:

- Analyze code
- Review code
- Generate draft converted code
- Generate notebook structure
- Show diff
- Require human approval
- No direct execution

Helix Migration generates draft migration code, notebook structures, validation plans, and reconciliation reports that must be reviewed and approved by humans before production use.

## Future Sandbox Execution

If execution is added later, it must use:

- Isolated containers
- No host filesystem access by default
- Resource limits
- Network restrictions
- Timeouts
- Secret isolation
- Audit logs
- Explicit admin enablement

