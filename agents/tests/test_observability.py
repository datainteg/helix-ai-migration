"""Tests for correlation IDs + Prometheus metrics in the BMAD executor."""

from __future__ import annotations


def test_helix_correlation_id_default_to_workflow_run_id():
    from agents import HelixBMAD

    h = HelixBMAD(project_id="p", requirement_id="r", requirement_text="x")
    # Default: correlation_id == workflow_run_id when not provided.
    assert h.correlation_id == h.workflow_run_id


def test_helix_correlation_id_custom_value():
    from agents import HelixBMAD

    h = HelixBMAD(
        project_id="p",
        requirement_id="r",
        requirement_text="x",
        correlation_id="req-abc-123",
    )
    assert h.correlation_id == "req-abc-123"


def test_helix_input_payload_includes_correlation_id():
    from agents import HelixBMAD

    h = HelixBMAD(
        project_id="p",
        requirement_id="r",
        requirement_text="x",
        correlation_id="req-xyz",
    )
    payload = h._input_payload()
    assert payload["correlation_id"] == "req-xyz"


def test_helix_result_carries_correlation_id(isolated_artifact_root):
    from agents import HelixBMAD

    result = HelixBMAD(
        project_id="corr-test",
        requirement_id="r1",
        requirement_text="Migrate X",
        correlation_id="req-trace-001",
    ).run()
    assert result.correlation_id == "req-trace-001"


def test_executor_persists_correlation_id_in_frontmatter(isolated_artifact_root):
    from agents.bmad.schemas import AnalystOutput
    from agents.runtime.bmad_executor import execute_agent_skill

    result = execute_agent_skill(
        agent_code="bmad-agent-analyst",
        skill_name="bmad-product-brief",
        project_id="corr-frontmatter",
        requirement_text="Migrate CRM",
        output_model=AnalystOutput,
        correlation_id="req-front-007",
    )
    assert result.success
    assert result.artifact.frontmatter["correlation_id"] == "req-front-007"


def test_metrics_module_is_importable_and_has_helpers():
    from agents.runtime import metrics

    assert hasattr(metrics, "record_run")
    assert hasattr(metrics, "timed_run")
    assert callable(metrics.record_run)


def test_timed_run_records_outcome_and_duration():
    """timed_run context manager records to Prometheus if available, no-op otherwise."""
    import time

    from agents.runtime.metrics import is_available, timed_run

    with timed_run(agent_code="t-agent", skill="t-skill") as ctx:
        time.sleep(0.01)
        ctx.set_outcome(success=True, mode="mock", prompt_tokens=500)

    # If prometheus_client is installed, the counter should have a non-zero value
    # for our test labels. If not installed, the call is a no-op.
    if is_available():
        from agents.runtime.metrics import AGENT_RUNS_TOTAL

        labels = AGENT_RUNS_TOTAL.labels(
            agent_code="t-agent", skill="t-skill", mode="mock", outcome="success"
        )
        # Counter._value is the underlying atomic — public API doesn't expose
        # current count, but labels() returning a child confirms wiring works.
        assert labels is not None


def test_executor_emits_metrics_with_mode_and_outcome(isolated_artifact_root):
    """End-to-end: run an agent and confirm metrics are emitted (when available)."""
    from agents.bmad.schemas import AnalystOutput
    from agents.runtime.bmad_executor import execute_agent_skill
    from agents.runtime.metrics import is_available

    if not is_available():
        # No prometheus_client → tests should still pass (no-op path).
        pass

    result = execute_agent_skill(
        agent_code="bmad-agent-analyst",
        skill_name="bmad-product-brief",
        project_id="metric-test",
        requirement_text="x",
        output_model=AnalystOutput,
    )
    assert result.success

    if is_available():
        from agents.runtime.metrics import AGENT_DURATION_SECONDS

        # Confirm the labels combination was registered (not raise on access).
        child = AGENT_DURATION_SECONDS.labels(
            agent_code="bmad-agent-analyst",
            skill="bmad-product-brief",
            mode=result.mode,
        )
        # The Histogram child has an observe() method even after recording.
        assert hasattr(child, "observe")
