# Temporal worker activities — stubs for Task 9
# Full Temporal integration follows in later infrastructure tasks.

from agents.bmad.workflow import run_bmad_workflow


async def execute_bmad_workflow(project_id: str, requirement_id: str) -> dict:
    """Temporal activity: execute BMAD planning workflow."""
    return run_bmad_workflow(project_id, requirement_id)


async def approve_workflow_step(workflow_id: str, decision: str, notes: str) -> dict:
    """Temporal activity: record human approval decision."""
    return {"workflow_id": workflow_id, "decision": decision, "notes": notes}
