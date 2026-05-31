"""Canonical stage-gated migration lifecycle constants (single source of truth).

The enterprise lifecycle converts the linear BMAD pipeline into discrete,
human-gated STAGES. Each stage runs an agent, produces an artifact, and waits
for review/approval before the next stage starts. Stage execution is driven by
a DB state machine (not one long-lived Temporal workflow) — each stage is a
short agent run; approval is an API/DB action that advances the machine.

Reuses the existing BMAD agent personas:
  project_context · analyst=Mary · architect=Winston · pm=John ·
  ux_designer=Sally · dev=Amelia · qa · tech_writer=Paige
"""
from __future__ import annotations

# ── Stage keys (closed enum) ─────────────────────────────────────────
PROJECT_CONTEXT = "PROJECT_CONTEXT"
BUSINESS_ANALYSIS = "BUSINESS_ANALYSIS"
ARCHITECTURE = "ARCHITECTURE"
PROJECT_PLANNING = "PROJECT_PLANNING"
UX_DESIGN = "UX_DESIGN"
SPRINT_GENERATION = "SPRINT_GENERATION"
SPRINT_EXECUTION = "SPRINT_EXECUTION"
DEVELOPMENT = "DEVELOPMENT"
VALIDATION = "VALIDATION"
RECONCILIATION = "RECONCILIATION"
SIGN_OFF = "SIGN_OFF"
DOCUMENTATION = "DOCUMENTATION"
CLOSURE = "CLOSURE"

STAGE_KEYS: tuple[str, ...] = (
    PROJECT_CONTEXT, BUSINESS_ANALYSIS, ARCHITECTURE, PROJECT_PLANNING, UX_DESIGN,
    SPRINT_GENERATION, SPRINT_EXECUTION, DEVELOPMENT, VALIDATION, RECONCILIATION,
    SIGN_OFF, DOCUMENTATION, CLOSURE,
)

# ── Stage statuses (state machine) ───────────────────────────────────
STAGE_STATUSES: tuple[str, ...] = (
    "not_started", "running", "generated", "under_review", "edit_requested",
    "resubmitted", "approved", "rejected", "completed", "failed", "skipped",
)
# Statuses that count a stage as "done" for advancing the lifecycle.
STAGE_DONE_STATUSES: frozenset[str] = frozenset({"approved", "completed", "skipped"})
# Statuses an approval can act on.
STAGE_REVIEWABLE_STATUSES: frozenset[str] = frozenset({"generated", "under_review", "resubmitted"})

# ── Project lifecycle status ─────────────────────────────────────────
LIFECYCLE_NOT_STARTED = "not_started"
LIFECYCLE_IN_PROGRESS = "in_progress"
LIFECYCLE_BLOCKED = "blocked"
LIFECYCLE_COMPLETED = "completed"
LIFECYCLE_CLOSED = "closed"

# ── Per-stage definition: agent persona + optionality + whether it gates ──
# `agent` uses the existing llm_agent_mappings agent_type codes (or a sentinel
# for orchestration/human/system stages). `optional` stages can be skipped.
# `artifact_type` is the canonical artifact this stage produces.
DEFAULT_LIFECYCLE: list[dict] = [
    {"key": PROJECT_CONTEXT,   "name": "Project Context",   "agent": "project_context",     "optional": False, "artifact_type": "project-context"},
    {"key": BUSINESS_ANALYSIS, "name": "Business Analysis", "agent": "bmad-agent-analyst",   "optional": False, "artifact_type": "business-analysis"},
    {"key": ARCHITECTURE,      "name": "Architecture",      "agent": "bmad-agent-architect", "optional": False, "artifact_type": "architecture"},
    {"key": PROJECT_PLANNING,  "name": "Project Planning",  "agent": "bmad-agent-pm",        "optional": False, "artifact_type": "project-plan"},
    {"key": UX_DESIGN,         "name": "UX Design",         "agent": "bmad-agent-ux-designer", "optional": True, "artifact_type": "ux-plan"},
    {"key": SPRINT_GENERATION, "name": "Sprint Generation", "agent": "bmad-agent-pm",        "optional": False, "artifact_type": "sprint-plan"},
    {"key": SPRINT_EXECUTION,  "name": "Sprint Execution",  "agent": "__orchestration__",    "optional": False, "artifact_type": "sprint-execution"},
    {"key": DEVELOPMENT,       "name": "Development",       "agent": "bmad-agent-dev",       "optional": False, "artifact_type": "implementation-plan"},
    {"key": VALIDATION,        "name": "Validation",        "agent": "qa",                   "optional": False, "artifact_type": "validation-plan"},
    {"key": RECONCILIATION,    "name": "Reconciliation",    "agent": "recon",                "optional": False, "artifact_type": "recon-plan"},
    {"key": SIGN_OFF,          "name": "Sign-off",          "agent": "__human__",            "optional": False, "artifact_type": "signoff"},
    {"key": DOCUMENTATION,     "name": "Documentation",     "agent": "bmad-agent-tech-writer", "optional": False, "artifact_type": "final-docs"},
    {"key": CLOSURE,           "name": "Closure",           "agent": "__system__",           "optional": False, "artifact_type": "closure-report"},
]

STAGE_NAME_BY_KEY: dict[str, str] = {s["key"]: s["name"] for s in DEFAULT_LIFECYCLE}
STAGE_AGENT_BY_KEY: dict[str, str] = {s["key"]: s["agent"] for s in DEFAULT_LIFECYCLE}
STAGE_ARTIFACT_TYPE_BY_KEY: dict[str, str] = {s["key"]: s["artifact_type"] for s in DEFAULT_LIFECYCLE}


def is_valid_stage(stage_key: str) -> bool:
    return stage_key in STAGE_KEYS
