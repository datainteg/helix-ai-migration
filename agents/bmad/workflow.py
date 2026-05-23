from agents.bmad.graph import run_bmad_graph


def run_bmad_workflow(
    project_id: str,
    requirement_id: str,
    organization_id: str | None = None,
    requirement_text: str | None = None,
    approval_decision: str | None = None,
) -> dict:
    return run_bmad_graph(
        project_id=project_id,
        requirement_id=requirement_id,
        organization_id=organization_id,
        requirement_text=requirement_text,
        approval_decision=approval_decision,
    )
