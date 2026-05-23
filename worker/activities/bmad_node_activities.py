"""Per-node Temporal activities for BMAD workflow.

Each BMAD agent runs as its own activity: retry, timeout, and heartbeat
are scoped per agent rather than the entire graph.
"""

from __future__ import annotations

import logging
from typing import Any

from temporalio import activity

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL = 30  # seconds


def _run_agent_node(agent_name: str, input_data: dict[str, Any]) -> dict[str, Any]:
    from agents.runtime.llm_client import call_llm
    from agents.bmad.official_agents import get_official_agent_metadata
    from agents.bmad.graph import build_mock_agent_result

    org_id = input_data.get("organization_id")
    requirement_text = input_data.get("requirement_text", "")
    agent_meta = get_official_agent_metadata(agent_name)

    system_prompt = (
        f"You are {agent_meta['name']}, the {agent_meta['title']}.\n"
        f"Phase: {agent_meta['phase']}\n"
        f"Description: {agent_meta['description']}"
    )
    user_prompt = f"Requirement:\n{requirement_text}\n\nGenerate structured output for your role."

    result = call_llm(agent_name, system_prompt, user_prompt, org_id=org_id)
    if result is None:
        result = build_mock_agent_result(agent_name, requirement_text)

    return {"agent": agent_name, "output": result, "status": "completed"}


@activity.defn
async def run_business_analyst_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    activity.heartbeat("ba_started")
    result = _run_agent_node("business_analyst", input_data)
    activity.heartbeat("ba_completed")
    logger.info("BA activity completed project=%s", input_data.get("project_id"))
    return result


@activity.defn
async def run_architect_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    activity.heartbeat("architect_started")
    result = _run_agent_node("architect", input_data)
    activity.heartbeat("architect_completed")
    logger.info("Architect activity completed project=%s", input_data.get("project_id"))
    return result


@activity.defn
async def run_validation_planner_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    activity.heartbeat("vp_started")
    result = _run_agent_node("qa_validation", input_data)
    activity.heartbeat("vp_completed")
    logger.info("VP activity completed project=%s", input_data.get("project_id"))
    return result


@activity.defn
async def run_pm_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    activity.heartbeat("pm_started")
    result = _run_agent_node("pm", input_data)
    activity.heartbeat("pm_completed")
    logger.info("PM activity completed project=%s", input_data.get("project_id"))
    return result


@activity.defn
async def persist_workflow_step_activity(step_data: dict[str, Any]) -> None:
    """Persist an agent step result to the database."""
    import json
    from app.db.session import SessionLocal
    from app.services.workflow_service import save_workflow_step

    db = SessionLocal()
    try:
        save_workflow_step(
            db,
            workflow_run_id=step_data["workflow_run_id"],
            agent_name=step_data["agent_name"],
            step_order=step_data["step_order"],
            status=step_data.get("status", "completed"),
            raw_output=json.dumps(step_data.get("output", {})),
            parsed_output_json=step_data.get("output"),
        )
    finally:
        db.close()
