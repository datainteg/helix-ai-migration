import os
import tomllib
from dataclasses import asdict, dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class BMADAgentReference:
    key: str
    name: str
    title: str
    phase: str
    skill_id: str
    command: str
    skill_path: str
    customize_path: str
    description: str
    source: str = "official_reference"
    bmad_root: str | None = None
    resolved_skill_path: str | None = None
    resolved_customize_path: str | None = None


# BMAD Method ships named agents as skills, not importable Python classes.
# These paths match the official BMAD-METHOD repository layout.
OFFICIAL_BMAD_AGENT_REFERENCES: dict[str, BMADAgentReference] = {
    # ── Phase 1: Analysis ──
    "business_analyst": BMADAgentReference(
        key="business_analyst",
        name="Mary",
        title="Business Analyst",
        phase="Analysis",
        skill_id="bmad-agent-analyst",
        command="bmad-analyst",
        skill_path="src/bmm-skills/1-analysis/bmad-agent-analyst/SKILL.md",
        customize_path="src/bmm-skills/1-analysis/bmad-agent-analyst/customize.toml",
        description="Strategic business analyst and requirements expert.",
    ),
    "tech_writer": BMADAgentReference(
        key="tech_writer",
        name="Paige",
        title="Technical Writer",
        phase="Analysis",
        skill_id="bmad-agent-tech-writer",
        command="bmad-tech-writer",
        skill_path="src/bmm-skills/1-analysis/bmad-agent-tech-writer/SKILL.md",
        customize_path="src/bmm-skills/1-analysis/bmad-agent-tech-writer/customize.toml",
        description="Technical documentation specialist and knowledge curator.",
    ),
    # ── Phase 2: Plan & Workflows ──
    "pm": BMADAgentReference(
        key="pm",
        name="John",
        title="Product Manager",
        phase="Plan-Workflows",
        skill_id="bmad-agent-pm",
        command="bmad-pm",
        skill_path="src/bmm-skills/2-plan-workflows/bmad-agent-pm/SKILL.md",
        customize_path="src/bmm-skills/2-plan-workflows/bmad-agent-pm/customize.toml",
        description="Product manager for PRD creation and requirements discovery.",
    ),
    "ux_designer": BMADAgentReference(
        key="ux_designer",
        name="Sally",
        title="UX Designer",
        phase="Plan-Workflows",
        skill_id="bmad-agent-ux-designer",
        command="bmad-ux-designer",
        skill_path="src/bmm-skills/2-plan-workflows/bmad-agent-ux-designer/SKILL.md",
        customize_path="src/bmm-skills/2-plan-workflows/bmad-agent-ux-designer/customize.toml",
        description="UX designer and UI specialist for interaction design and user flows.",
    ),
    # ── Phase 3: Solutioning ──
    "architect": BMADAgentReference(
        key="architect",
        name="Winston",
        title="System Architect",
        phase="Solutioning",
        skill_id="bmad-agent-architect",
        command="bmad-architect",
        skill_path="src/bmm-skills/3-solutioning/bmad-agent-architect/SKILL.md",
        customize_path="src/bmm-skills/3-solutioning/bmad-agent-architect/customize.toml",
        description="System architect and technical design leader.",
    ),
    # ── Phase 4: Implementation ──
    "data_engineer": BMADAgentReference(
        key="data_engineer",
        name="Amelia",
        title="Senior Software Engineer",
        phase="Implementation",
        skill_id="bmad-agent-dev",
        command="bmad-dev",
        skill_path="src/bmm-skills/4-implementation/bmad-agent-dev/SKILL.md",
        customize_path="src/bmm-skills/4-implementation/bmad-agent-dev/customize.toml",
        description="Senior software engineer for story execution and code implementation with test-first discipline.",
    ),
    "qa_validation": BMADAgentReference(
        key="qa_validation",
        name="QA Bot",
        title="QA Automation Engineer",
        phase="Implementation",
        skill_id="bmad-qa-generate-e2e-tests",
        command="bmad-qa",
        skill_path="src/bmm-skills/4-implementation/bmad-qa-generate-e2e-tests/SKILL.md",
        customize_path="src/bmm-skills/4-implementation/bmad-qa-generate-e2e-tests/customize.toml",
        description="Generate automated E2E and API tests for validation and quality assurance.",
    ),
    "recon": BMADAgentReference(
        key="recon",
        name="Code Reviewer",
        title="Elite Code Reviewer",
        phase="Implementation",
        skill_id="bmad-code-review",
        command="bmad-review",
        skill_path="src/bmm-skills/4-implementation/bmad-code-review/SKILL.md",
        customize_path="src/bmm-skills/4-implementation/bmad-code-review/customize.toml",
        description="Adversarial code review with parallel review layers and structured triage for reconciliation.",
    ),
    "devops": BMADAgentReference(
        key="devops",
        name="DevOps Bot",
        title="DevOps Engineer",
        phase="Implementation",
        skill_id="helix-devops",
        command="helix-devops",
        skill_path="agents/bmad/custom/devops/SKILL.md",
        customize_path="agents/bmad/custom/devops/customize.toml",
        description="DevOps engineer for CI/CD, deployment orchestration, and infrastructure automation. (Custom Helix agent — no direct BMAD equivalent.)",
    ),
    # ── Core Skills: Multi-Agent Orchestration & Analysis ──
    "party_mode": BMADAgentReference(
        key="party_mode",
        name="Party Mode",
        title="Multi-Agent Orchestrator",
        phase="Core",
        skill_id="bmad-party-mode",
        command="bmad-party",
        skill_path="src/core-skills/bmad-party-mode/SKILL.md",
        customize_path="src/core-skills/bmad-party-mode/customize.toml",
        description="Orchestrates roundtable discussions between BMAD agents — each spawned as independent subagents for genuine diversity of thought.",
    ),
    "brainstorming": BMADAgentReference(
        key="brainstorming",
        name="Brainstorming",
        title="Creative Ideation Facilitator",
        phase="Core",
        skill_id="bmad-brainstorming",
        command="bmad-brainstorm",
        skill_path="src/core-skills/bmad-brainstorming/SKILL.md",
        customize_path="src/core-skills/bmad-brainstorming/customize.toml",
        description="Interactive brainstorming sessions using diverse creative techniques and ideation methods.",
    ),
    "distillator": BMADAgentReference(
        key="distillator",
        name="Distillator",
        title="Document Compression Engine",
        phase="Core",
        skill_id="bmad-distillator",
        command="bmad-distill",
        skill_path="src/core-skills/bmad-distillator/SKILL.md",
        customize_path="src/core-skills/bmad-distillator/customize.toml",
        description="Lossless LLM-optimized compression of source documents — preserves every fact, decision, constraint, and relationship.",
    ),
    "advanced_elicitation": BMADAgentReference(
        key="advanced_elicitation",
        name="Advanced Elicitation",
        title="Deep Critique Engine",
        phase="Core",
        skill_id="bmad-advanced-elicitation",
        command="bmad-elicit",
        skill_path="src/core-skills/bmad-advanced-elicitation/SKILL.md",
        customize_path="src/core-skills/bmad-advanced-elicitation/customize.toml",
        description="Push LLM output through deeper critique: Socratic, first principles, pre-mortem, red team methods.",
    ),
}


def _configured_bmad_root() -> Path | None:
    root = os.getenv("BMAD_METHOD_ROOT")
    if root:
        return Path(root).expanduser().resolve()

    vendored_root = Path(__file__).resolve().parent / "BMAD-METHOD"
    if vendored_root.is_dir():
        return vendored_root

    return None


def _read_skill_description(skill_path: Path) -> str | None:
    for line in skill_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("description:"):
            return line.removeprefix("description:").strip()
    return None


def load_official_bmad_agent(agent_key: str, bmad_root: Path | None = None) -> BMADAgentReference:
    reference = OFFICIAL_BMAD_AGENT_REFERENCES[agent_key]
    root = bmad_root or _configured_bmad_root()
    if root is None:
        return reference

    skill_path = root / reference.skill_path
    customize_path = root / reference.customize_path
    if not skill_path.is_file() or not customize_path.is_file():
        return reference

    customize = tomllib.loads(customize_path.read_text(encoding="utf-8"))
    agent_config = customize.get("agent", {})
    description = _read_skill_description(skill_path) or reference.description

    return replace(
        reference,
        name=agent_config.get("name", reference.name),
        title=agent_config.get("title", reference.title),
        description=description,
        source="official_bmad_skill",
        bmad_root=str(root),
        resolved_skill_path=str(skill_path),
        resolved_customize_path=str(customize_path),
    )


def get_official_agent_metadata(agent_key: str, bmad_root: Path | None = None) -> dict:
    return asdict(load_official_bmad_agent(agent_key, bmad_root))
