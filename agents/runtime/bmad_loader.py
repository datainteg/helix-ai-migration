"""BMAD-METHOD loader.

Wraps the BMAD installer's own resolvers (`_bmad/scripts/resolve_config.py` and
`_bmad/scripts/resolve_customization.py`) so the rest of the Helix runtime can
load BMAD agents and skills without duplicating BMAD's merge logic.

Project layout assumed (created by `bmad install`):

  {project-root}/
    _bmad/
      config.toml                 # base team config (regenerated on install)
      config.user.toml            # base user config (regenerated on install)
      bmm/config.yaml             # BMM module config
      custom/                     # team + user overrides (never overwritten)
      scripts/resolve_config.py
      scripts/resolve_customization.py
    agents/bmad/BMAD-METHOD/      # vendored BMAD source (skills + scripts)
      src/bmm-skills/<phase>/<skill>/{SKILL.md, customize.toml, ...}
      src/core-skills/<skill>/{SKILL.md, customize.toml, ...}

Output: dataclasses describing fully merged agents/skills, plus loaded SKILL.md
bodies. Persistent-fact globs are resolved against the project root.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT_DEFAULT = _THIS_FILE.parents[2]  # agents/runtime/bmad_loader.py -> repo root

# SC-052 — pinned sha256 manifest of the vendored BMAD installer scripts we
# execute via subprocess. Computed from the scripts at vendoring time. Before
# running a script we re-hash the on-disk bytes and refuse to execute on
# mismatch (or for any script not in this manifest), falling back to the
# in-process tomllib path. This stops a planted/tampered `resolve_config.py`
# in the BMAD dir from running arbitrary code with the worker's privileges.
# Override the policy with HELIX_BMAD_SCRIPT_HASH_ENFORCE=warn (log + run) or
# =off (skip the check) — default is fail-closed (fall back to tomllib).
# To re-pin after a legitimate BMAD upgrade, recompute:
#   python -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('_bmad/scripts/resolve_config.py').read_bytes()).hexdigest())"
_BMAD_SCRIPT_HASHES: dict[str, str] = {
    "resolve_config.py": "8e326149d9170477ecc21aa2aa2389d8fbaa5d1cd95db2de2ad33029ce8ae528",
    "resolve_customization.py": "6dbf36a2fea13392426fdbaf4f074b6d9b93488a964d2d1bff2a5c1c3a1d506e",
}


def _script_checksum_ok(script_name: str, script_path: Path) -> bool:
    """SC-052 — verify a vendored BMAD script matches its pinned sha256.

    Returns True when the script is safe to execute. On mismatch / unknown
    script the caller should fall back to the in-process tomllib path (we
    return False) unless the operator relaxed the policy via
    ``HELIX_BMAD_SCRIPT_HASH_ENFORCE``:
      - ``off``  → skip the check entirely (return True)
      - ``warn`` → log a warning on mismatch but still allow execution
      - default  → fail-closed (return False → fall back to tomllib)
    """
    policy = os.getenv("HELIX_BMAD_SCRIPT_HASH_ENFORCE", "").strip().lower()
    if policy == "off":
        return True

    expected = _BMAD_SCRIPT_HASHES.get(script_name)
    if expected is None:
        logger.warning(
            "BMAD script %s is not in the pinned-hash manifest — refusing to "
            "execute it; using on-disk defaults instead.",
            script_name,
        )
        return policy == "warn"

    try:
        actual = hashlib.sha256(script_path.read_bytes()).hexdigest()
    except OSError as exc:
        logger.warning("Could not read BMAD script %s for checksum: %s", script_path, exc)
        return False

    if actual != expected:
        logger.warning(
            "BMAD script %s sha256 mismatch (expected %s, got %s) — %s",
            script_name,
            expected,
            actual,
            "running anyway (enforce=warn)" if policy == "warn"
            else "refusing to execute; using on-disk defaults instead",
        )
        return policy == "warn"
    return True


def project_root() -> Path:
    """Resolve project root. Override with HELIX_PROJECT_ROOT env var (Docker)."""
    override = os.getenv("HELIX_PROJECT_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return _REPO_ROOT_DEFAULT


def bmad_method_root() -> Path:
    """Resolve the vendored BMAD-METHOD source root."""
    override = os.getenv("BMAD_METHOD_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return project_root() / "agents" / "bmad" / "BMAD-METHOD"


def bmad_install_dir() -> Path:
    """Resolve the installed `_bmad/` directory at the project root."""
    return project_root() / "_bmad"


# ── Dataclasses ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class BMADConfig:
    """Resolved BMAD central config (merged across 4 layers)."""

    raw: dict[str, Any]
    project_name: str
    user_name: str
    communication_language: str
    document_output_language: str
    output_folder: str  # absolute path (placeholders resolved)
    planning_artifacts: str
    implementation_artifacts: str
    project_knowledge: str


@dataclass
class BMADAgent:
    """Resolved BMAD agent — persona + customization."""

    code: str               # e.g. "bmad-agent-analyst"
    name: str               # e.g. "Mary"
    title: str              # e.g. "Business Analyst"
    icon: str               # e.g. "📊"
    phase: str              # "Analysis", "Plan-Workflows", "Solutioning", "Implementation"
    skill_path: Path        # absolute path to SKILL.md
    customize_path: Path    # absolute path to customize.toml
    skill_md: str           # full SKILL.md body
    customization: dict[str, Any] = field(default_factory=dict)
    role: str = ""
    identity: str = ""
    communication_style: str = ""
    principles: list[str] = field(default_factory=list)
    persistent_facts_literal: list[str] = field(default_factory=list)
    persistent_facts_files: list[Path] = field(default_factory=list)
    menu: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class BMADSkill:
    """A BMAD task skill (e.g. bmad-create-prd) — SKILL.md + customize.toml."""

    name: str               # e.g. "bmad-create-prd"
    phase: str              # phase folder name
    skill_path: Path
    customize_path: Path
    skill_md: str
    description: str = ""
    customization: dict[str, Any] = field(default_factory=dict)


# ── Path resolution helpers ─────────────────────────────────────────


_PHASE_DIRS = {
    "Analysis": "1-analysis",
    "Plan-Workflows": "2-plan-workflows",
    "Solutioning": "3-solutioning",
    "Implementation": "4-implementation",
    "Core": None,  # core skills live under src/core-skills
}


def _agent_phase(agent_code: str) -> str:
    """Heuristic mapping from agent code to phase folder name."""
    return {
        "bmad-agent-analyst": "Analysis",
        "bmad-agent-tech-writer": "Analysis",
        "bmad-agent-pm": "Plan-Workflows",
        "bmad-agent-ux-designer": "Plan-Workflows",
        "bmad-agent-architect": "Solutioning",
        "bmad-agent-dev": "Implementation",
    }.get(agent_code, "Implementation")


def _find_skill_dir(skill_name: str) -> Path | None:
    """Find a BMAD skill directory by name across bmm-skills phases and core-skills."""
    root = bmad_method_root() / "src"
    # Try bmm-skills phases
    for phase_dir in (root / "bmm-skills").glob("[0-9]-*"):
        candidate = phase_dir / skill_name
        if candidate.is_dir():
            return candidate
    # Try core-skills
    core = root / "core-skills" / skill_name
    if core.is_dir():
        return core
    return None


def _resolve_placeholders(value: str, *, project_root_path: Path) -> str:
    """Resolve {project-root} / {skill-root} style placeholders. Skill root not resolved here."""
    return value.replace("{project-root}", str(project_root_path))


# ── Subprocess wrappers around BMAD resolvers ───────────────────────


def _run_bmad_script(script_name: str, args: list[str]) -> dict[str, Any]:
    """Invoke a BMAD installer script via subprocess and parse its JSON stdout.

    Returns an empty dict on failure (logged). Callers should treat empty output as
    "no override available" and fall back to the raw on-disk customize.toml /
    config.toml.
    """
    script = bmad_install_dir() / "scripts" / script_name
    if not script.is_file():
        logger.warning("BMAD script not found at %s — using on-disk defaults only.", script)
        return {}

    # SC-052 — verify the script against its pinned sha256 before executing it.
    # On mismatch fall back to the caller's in-process tomllib path.
    if not _script_checksum_ok(script_name, script):
        return {}

    import sys

    cmd = [sys.executable, str(script), *args]
    # Force UTF-8 for the child process — BMAD scripts emit emoji and other
    # non-ASCII chars to stdout, which fails under Windows cp1252.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=15,
            env=env,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("BMAD script %s failed to run: %s", script_name, exc)
        return {}

    if result.returncode != 0:
        logger.warning(
            "BMAD script %s exited %s: %s",
            script_name,
            result.returncode,
            result.stderr.strip()[:500],
        )
        return {}

    text = result.stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("BMAD script %s output not valid JSON: %s", script_name, exc)
        return {}


# ── Public API ───────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def load_bmad_config() -> BMADConfig:
    """Load the merged BMAD config from the installed _bmad/ directory."""
    root = project_root()
    merged = _run_bmad_script("resolve_config.py", ["--project-root", str(root)])

    # Fallback: read all 4 config.toml layers directly + deep-merge.
    if not merged:
        import tomllib

        def _deep_merge(base: dict, override: dict) -> dict:
            out = dict(base)
            for k, v in override.items():
                if isinstance(v, dict) and isinstance(out.get(k), dict):
                    out[k] = _deep_merge(out[k], v)
                else:
                    out[k] = v
            return out

        merged = {}
        for f in (
            bmad_install_dir() / "config.toml",
            bmad_install_dir() / "config.user.toml",
            bmad_install_dir() / "custom" / "config.toml",
            bmad_install_dir() / "custom" / "config.user.toml",
        ):
            if f.is_file():
                try:
                    with f.open("rb") as fh:
                        merged = _deep_merge(merged, tomllib.load(fh))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to read %s: %s", f, exc)

    core = merged.get("core", {}) if isinstance(merged, dict) else {}
    modules_bmm = merged.get("modules", {}).get("bmm", {}) if isinstance(merged, dict) else {}

    def _resolve(value: str | None, default: str) -> str:
        if not value:
            return default
        return _resolve_placeholders(value, project_root_path=root)

    output_folder = _resolve(core.get("output_folder"), str(root / "_bmad-output"))
    planning = _resolve(modules_bmm.get("planning_artifacts"), f"{output_folder}/planning-artifacts")
    impl = _resolve(modules_bmm.get("implementation_artifacts"), f"{output_folder}/implementation-artifacts")
    knowledge = _resolve(modules_bmm.get("project_knowledge"), str(root / "docs"))

    return BMADConfig(
        raw=merged,
        project_name=core.get("project_name", "Helix Migration"),
        user_name=core.get("user_name", "helix"),
        communication_language=core.get("communication_language", "English"),
        document_output_language=core.get("document_output_language", "English"),
        output_folder=output_folder,
        planning_artifacts=planning,
        implementation_artifacts=impl,
        project_knowledge=knowledge,
    )


@lru_cache(maxsize=32)
def load_bmad_agent(agent_code: str) -> BMADAgent:
    """Load a BMAD agent — resolves SKILL.md and merged customize.toml."""
    skill_dir = _find_skill_dir(agent_code)
    if skill_dir is None:
        raise FileNotFoundError(f"BMAD agent skill not found for code={agent_code!r}")

    skill_md_path = skill_dir / "SKILL.md"
    customize_path = skill_dir / "customize.toml"
    if not skill_md_path.is_file():
        raise FileNotFoundError(f"SKILL.md missing for agent={agent_code} at {skill_md_path}")

    skill_md = skill_md_path.read_text(encoding="utf-8")

    # Resolved customization via BMAD's own merger; falls back to raw customize.toml.
    merged = _run_bmad_script(
        "resolve_customization.py",
        ["--skill", str(skill_dir)],
    )
    if not merged:
        import tomllib

        try:
            with customize_path.open("rb") as fh:
                merged = tomllib.load(fh)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falling back to empty customization for %s: %s", agent_code, exc)
            merged = {}

    agent_block = merged.get("agent", {}) if isinstance(merged, dict) else {}

    persistent_facts_literal: list[str] = []
    persistent_facts_files: list[Path] = []
    root = project_root()
    for entry in agent_block.get("persistent_facts", []) or []:
        if isinstance(entry, str) and entry.startswith("file:"):
            raw = entry[len("file:") :]
            raw = _resolve_placeholders(raw, project_root_path=root)
            for path in root.glob(raw.removeprefix(str(root)).lstrip("/\\")) if "*" in raw else [Path(raw)]:
                if path.is_file():
                    persistent_facts_files.append(path)
        elif isinstance(entry, str):
            persistent_facts_literal.append(entry)

    return BMADAgent(
        code=agent_code,
        name=agent_block.get("name", agent_code),
        title=agent_block.get("title", ""),
        icon=agent_block.get("icon", ""),
        phase=_agent_phase(agent_code),
        skill_path=skill_md_path,
        customize_path=customize_path,
        skill_md=skill_md,
        customization=merged,
        role=agent_block.get("role", ""),
        identity=agent_block.get("identity", ""),
        communication_style=agent_block.get("communication_style", ""),
        principles=list(agent_block.get("principles", []) or []),
        persistent_facts_literal=persistent_facts_literal,
        persistent_facts_files=persistent_facts_files,
        menu=list(agent_block.get("menu", []) or []),
    )


@lru_cache(maxsize=128)
def load_bmad_skill(skill_name: str) -> BMADSkill:
    """Load a BMAD task skill (e.g. bmad-create-prd) by name."""
    skill_dir = _find_skill_dir(skill_name)
    if skill_dir is None:
        raise FileNotFoundError(f"BMAD skill not found for name={skill_name!r}")

    skill_md_path = skill_dir / "SKILL.md"
    customize_path = skill_dir / "customize.toml"

    skill_md = skill_md_path.read_text(encoding="utf-8") if skill_md_path.is_file() else ""

    description = ""
    front = re.match(r"^---\s*\n(.*?)\n---\s*\n", skill_md, re.DOTALL)
    if front:
        for line in front.group(1).splitlines():
            if line.startswith("description:"):
                description = line.removeprefix("description:").strip()
                break

    customization: dict[str, Any] = {}
    if customize_path.is_file():
        import tomllib

        try:
            with customize_path.open("rb") as fh:
                customization = tomllib.load(fh)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse customize.toml for skill %s: %s", skill_name, exc)

    return BMADSkill(
        name=skill_name,
        phase=skill_dir.parent.name,
        skill_path=skill_md_path,
        customize_path=customize_path,
        skill_md=skill_md,
        description=description,
        customization=customization,
    )


def build_persona_prompt(agent: BMADAgent) -> str:
    """Compose a persona system prompt from a BMAD agent's SKILL.md + customization.

    The SKILL.md "Overview" section establishes baseline identity. Customization
    layers (role, identity, communication_style, principles) follow BMAD's own
    activation-step semantics (see Step 3 in any agent's SKILL.md).
    """
    # Extract Overview section from SKILL.md (between "## Overview" and next "## ").
    overview = ""
    match = re.search(r"##\s*Overview\s*\n(.+?)(?=\n##\s|\Z)", agent.skill_md, re.DOTALL)
    if match:
        overview = match.group(1).strip()

    lines: list[str] = []
    if overview:
        lines.append(overview)

    if agent.role:
        lines.append(f"\nAdditional role: {agent.role}")
    if agent.identity:
        lines.append(f"Identity: {agent.identity}")
    if agent.communication_style:
        lines.append(f"Communication style: {agent.communication_style}")
    if agent.principles:
        lines.append("\nPrinciples:")
        for p in agent.principles:
            lines.append(f"  - {p}")

    if agent.persistent_facts_literal:
        lines.append("\nPersistent facts:")
        for f in agent.persistent_facts_literal:
            lines.append(f"  - {f}")

    return "\n".join(lines).strip()


def build_skill_instructions(skill: BMADSkill) -> str:
    """Extract LLM-actionable instructions from a BMAD task skill's SKILL.md.

    Skips the YAML frontmatter; returns the markdown body.
    """
    text = skill.skill_md
    # Drop YAML frontmatter (--- ... ---) if present.
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL)
    return body.strip()


def clear_cache() -> None:
    """Reset all internal caches. Useful in tests + when configs change."""
    load_bmad_config.cache_clear()
    load_bmad_agent.cache_clear()
    load_bmad_skill.cache_clear()
