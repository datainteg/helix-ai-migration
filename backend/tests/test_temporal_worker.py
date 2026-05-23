"""Tests for Prompt 8: Temporal workflow/activity/worker skeleton.

Unit tests do NOT require a real Temporal server.
Integration tests are skipped if Temporal is unavailable.
"""

import asyncio
import os

import pytest

# Patch environment before any temporalio imports to prevent
# connection attempts during unit tests
os.environ.setdefault("TEMPORAL_ADDRESS", "localhost:7233")


# ── Activity unit tests (no Temporal server) ─────────────────────────

class TestBmadActivity:
    """Test the BMAD activity function directly — no Temporal runtime."""

    def test_activity_is_decorated_with_defn(self):
        from worker.activities.bmad_activities import execute_bmad_graph_activity

        # The @activity.defn decorator sets __temporal_activity_definition
        assert hasattr(execute_bmad_graph_activity, "__temporal_activity_definition")

    @pytest.mark.asyncio
    async def test_activity_calls_run_bmad_graph_and_returns_output(self):
        from worker.activities.bmad_activities import execute_bmad_graph_activity

        input_data = {
            "project_id": "project-1",
            "requirement_id": "requirement-1",
            "organization_id": "org-1",
            "requirement_text": "Migrate CRM data from Oracle to Snowflake",
            "approval_decision": None,
        }

        result = await execute_bmad_graph_activity(input_data)

        assert result["status"] == "completed"
        assert result["current_agent"] == "approval_gate"
        assert result["approval_required"] is True
        assert result["errors"] == []
        assert set(result["outputs"].keys()) == {
            "business_analyst", "architect", "validation_planner", "approval_gate",
        }

    @pytest.mark.asyncio
    async def test_activity_returns_final_output(self):
        from worker.activities.bmad_activities import execute_bmad_graph_activity

        result = await execute_bmad_graph_activity({
            "project_id": "p1",
            "requirement_id": "r1",
        })

        assert result["final_output"] is not None
        assert result["final_output"]["status"] == "completed"
        assert "business_analysis" in result["final_output"]
        assert "architecture" in result["final_output"]
        assert "validation_plan" in result["final_output"]

    @pytest.mark.asyncio
    async def test_activity_with_approved_decision(self):
        from worker.activities.bmad_activities import execute_bmad_graph_activity

        result = await execute_bmad_graph_activity({
            "project_id": "p1",
            "requirement_id": "r1",
            "approval_decision": "approved",
        })

        assert result["approval_required"] is False
        assert result["status"] == "completed"


# ── Workflow structure tests (no Temporal runtime) ───────────────────

class TestBmadWorkflow:
    """Test the BMAD workflow class structure — no Temporal server."""

    def test_workflow_is_decorated_with_defn(self):
        from worker.workflows.bmad_planning_workflow import BMADPlanningWorkflow

        assert hasattr(BMADPlanningWorkflow, "__temporal_workflow_definition")

    def test_workflow_has_run_method(self):
        from worker.workflows.bmad_planning_workflow import BMADPlanningWorkflow

        assert hasattr(BMADPlanningWorkflow, "run")
        assert callable(BMADPlanningWorkflow.run)


# ── Worker main module structure ─────────────────────────────────────

class TestWorkerMain:
    """Test worker main.py structure and imports."""

    def test_main_module_imports_workflow_and_activity(self):
        from worker.main import (
            BMADPlanningWorkflow,
            TASK_QUEUE,
            execute_bmad_graph_activity,
        )

        assert TASK_QUEUE == "helix-bmad-task-queue"
        assert BMADPlanningWorkflow is not None
        assert execute_bmad_graph_activity is not None

    def test_main_has_main_function(self):
        from worker.main import main

        assert asyncio.iscoroutinefunction(main)


# ── Integration test (skipped if Temporal unavailable) ───────────────

@pytest.mark.skipif(
    not os.environ.get("TEMPORAL_TEST_HOST"),
    reason="TEMPORAL_TEST_HOST not set — requires a running Temporal server",
)
class TestTemporalIntegration:
    """Integration tests requiring a real Temporal server."""

    async def test_worker_can_start_and_connect(self):
        """Verify the worker can connect to Temporal and start."""
        from temporalio.client import Client
        from temporalio.worker import Worker

        from worker.activities.bmad_activities import execute_bmad_graph_activity
        from worker.workflows.bmad_planning_workflow import BMADPlanningWorkflow

        host = os.environ["TEMPORAL_TEST_HOST"]
        client = await Client.connect(host)

        worker = Worker(
            client,
            task_queue="helix-bmad-test-queue",
            workflows=[BMADPlanningWorkflow],
            activities=[execute_bmad_graph_activity],
        )

        assert worker is not None
        await worker.shutdown()

    async def test_workflow_execution_end_to_end(self):
        """Execute a full BMAD workflow through Temporal."""
        import uuid

        from temporalio.client import Client

        from worker.workflows.bmad_planning_workflow import BMADPlanningWorkflow

        host = os.environ["TEMPORAL_TEST_HOST"]
        client = await Client.connect(host)

        result = await client.execute_workflow(
            BMADPlanningWorkflow.run,
            {
                "project_id": "test-p1",
                "requirement_id": "test-r1",
                "organization_id": "test-org",
                "requirement_text": "Integration test migration",
            },
            id=f"bmad-test-{uuid.uuid4().hex[:12]}",
            task_queue="helix-bmad-test-queue",
        )

        assert result["status"] == "completed"
        assert len(result["outputs"]) == 4
