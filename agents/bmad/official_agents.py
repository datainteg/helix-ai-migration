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


# BMAD Method ships named agents as skills, not importable Python classes.
# These paths match the official BMAD-METHOD repository layout.
OFFICIAL_BMAD_AGENT_REFERENCES: dict[str, BMADAgentReference] = {
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
}


def _configured_bmad_root() -> Path | None:
    root = os.getenv("BMAD_METHOD_ROOT")
    if not root:
        return None
    return Path(root).expanduser().resolve()


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
    )


def get_official_agent_metadata(agent_key: str, bmad_root: Path | None = None) -> dict:
    return asdict(load_official_bmad_agent(agent_key, bmad_root))
