"""Prometheus metrics for BMAD agent runs.

Metric names are exposed at the backend's `/metrics` endpoint (instrumented by
`prometheus-fastapi-instrumentator`). The worker emits to the same registry by
running in the same Python process tree — when run via Temporal each activity
process maintains its own metrics; aggregate via Prometheus server-side
sharding labels if you need a single dashboard.

If `prometheus_client` is not importable (e.g. it's an optional dep), all
helpers become no-ops so agents work fine without it.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


if _AVAILABLE:
    AGENT_RUNS_TOTAL = Counter(
        "helix_bmad_agent_runs_total",
        "Number of BMAD agent runs by agent, skill, mode, and outcome.",
        labelnames=["agent_code", "skill", "mode", "outcome"],
    )

    AGENT_DURATION_SECONDS = Histogram(
        "helix_bmad_agent_duration_seconds",
        "BMAD agent run duration in seconds.",
        labelnames=["agent_code", "skill", "mode"],
        # Buckets tuned for LLM-call latency: 0.5s (mock) → 60s (slow LLM).
        buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120),
    )

    AGENT_PROMPT_TOKENS = Histogram(
        "helix_bmad_agent_prompt_tokens",
        "Estimated prompt token count per BMAD agent run.",
        labelnames=["agent_code", "skill"],
        # Buckets from small (1K) to large (50K) prompts.
        buckets=(500, 1000, 2000, 4000, 8000, 16000, 32000, 50000),
    )


def record_run(
    *,
    agent_code: str,
    skill: str,
    mode: str,
    outcome: str,
    duration_seconds: float,
    prompt_tokens: int | None = None,
) -> None:
    """Record one completed agent run. Safe to call when prometheus_client is missing."""
    if not _AVAILABLE:
        return
    try:
        AGENT_RUNS_TOTAL.labels(agent_code=agent_code, skill=skill, mode=mode, outcome=outcome).inc()
        AGENT_DURATION_SECONDS.labels(agent_code=agent_code, skill=skill, mode=mode).observe(duration_seconds)
        if prompt_tokens is not None:
            AGENT_PROMPT_TOKENS.labels(agent_code=agent_code, skill=skill).observe(prompt_tokens)
    except Exception as exc:  # noqa: BLE001 — metrics never break the workflow
        logger.debug("metrics emit failed: %s", exc)


@contextmanager
def timed_run(*, agent_code: str, skill: str):
    """Context manager that times a block + lets the caller record outcome+mode.

    Usage:
        with timed_run(agent_code='bmad-agent-analyst', skill='bmad-product-brief') as ctx:
            result = do_work()
            ctx.set_outcome(success=True, mode='pydantic_ai', prompt_tokens=1234)
    """

    class _Ctx:
        def __init__(self) -> None:
            self._outcome = "unknown"
            self._mode = "unknown"
            self._prompt_tokens: int | None = None

        def set_outcome(self, *, success: bool, mode: str, prompt_tokens: int | None = None) -> None:
            self._outcome = "success" if success else "failure"
            self._mode = mode
            self._prompt_tokens = prompt_tokens

    ctx = _Ctx()
    started = time.monotonic()
    try:
        yield ctx
    finally:
        elapsed = time.monotonic() - started
        record_run(
            agent_code=agent_code,
            skill=skill,
            mode=ctx._mode,
            outcome=ctx._outcome,
            duration_seconds=elapsed,
            prompt_tokens=ctx._prompt_tokens,
        )


def is_available() -> bool:
    return _AVAILABLE
