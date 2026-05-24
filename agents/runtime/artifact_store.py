"""File-based artifact store for BMAD agent handoff.

BMAD's communication model is file-based: each agent writes markdown artifacts
to `planning_artifacts/` (or `implementation_artifacts/`) and downstream agents
read them as context. This module is the Python wrapper around that convention.

Layout under `planning_artifacts/`:

  {planning_artifacts}/
    {project_id}/
      {agent_code}/
        {YYYYMMDDTHHMMSS}-{slug}.md
        latest.json                 # index of latest artifact per filename slug

Each markdown artifact carries a YAML frontmatter block with provenance metadata
(agent, skill, project_id, requirement_id, llm_provider/model, timestamps) so
the next agent — and the backend persistence layer — can read structured fields
without parsing prose.

The store uses simple atomic writes (temp file + os.replace) so concurrent
LangGraph nodes don't truncate each other.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from agents.runtime.bmad_loader import load_bmad_config

logger = logging.getLogger(__name__)


@dataclass
class Artifact:
    """In-memory representation of a stored artifact."""

    path: Path
    agent_code: str
    skill: str
    project_id: str
    filename: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""

    def to_summary(self) -> dict[str, Any]:
        """Compact dict for embedding in another agent's user-prompt context."""
        return {
            "agent": self.agent_code,
            "skill": self.skill,
            "filename": self.filename,
            "frontmatter": self.frontmatter,
            "body": self.body,
        }


# ── Path helpers ─────────────────────────────────────────────────────


def _planning_root() -> Path:
    cfg = load_bmad_config()
    return Path(cfg.planning_artifacts).expanduser().resolve()


def _implementation_root() -> Path:
    cfg = load_bmad_config()
    return Path(cfg.implementation_artifacts).expanduser().resolve()


def _project_dir(project_id: str, phase: str = "planning") -> Path:
    base = _planning_root() if phase == "planning" else _implementation_root()
    return base / _slug(project_id)


def _agent_dir(project_id: str, agent_code: str, phase: str = "planning") -> Path:
    return _project_dir(project_id, phase=phase) / agent_code


def _slug(value: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", value or "")
    return s.strip("-") or "untitled"


# ── Frontmatter ─────────────────────────────────────────────────────


_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _dump_frontmatter(frontmatter: dict[str, Any]) -> str:
    """Minimal YAML-like frontmatter serializer (JSON-safe, no external dep)."""
    import yaml

    return yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()


def _parse_artifact(path: Path) -> tuple[dict[str, Any], str]:
    """Read an artifact file, returning (frontmatter, body)."""
    text = path.read_text(encoding="utf-8")
    match = _FRONT_RE.match(text)
    if not match:
        return {}, text
    front_raw, body = match.group(1), match.group(2)
    try:
        import yaml

        front = yaml.safe_load(front_raw) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Frontmatter parse failed for %s: %s", path, exc)
        front = {}
    return (front if isinstance(front, dict) else {}), body


# ── Public API ───────────────────────────────────────────────────────


def write_artifact(
    *,
    project_id: str,
    agent_code: str,
    skill: str,
    filename: str,
    body: str,
    frontmatter: dict[str, Any] | None = None,
    phase: str = "planning",
) -> Artifact:
    """Persist an artifact and update the latest-index."""
    if not project_id or not agent_code or not skill or not filename:
        raise ValueError("project_id, agent_code, skill, filename are all required")

    dir_path = _agent_dir(project_id, agent_code, phase=phase)
    dir_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = _slug(filename)
    base_name = f"{ts}-{slug}.md"
    full_path = dir_path / base_name

    merged_front: dict[str, Any] = {
        "agent": agent_code,
        "skill": skill,
        "project_id": project_id,
        "filename": slug,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if frontmatter:
        merged_front.update(frontmatter)

    text = f"---\n{_dump_frontmatter(merged_front)}\n---\n\n{body.strip()}\n"

    # Atomic write: temp file → rename
    fd, tmp_name = tempfile.mkstemp(prefix=".artifact-", dir=dir_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, full_path)
    except Exception:
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass
        raise

    _update_latest_index(dir_path, slug, full_path)

    artifact = Artifact(
        path=full_path,
        agent_code=agent_code,
        skill=skill,
        project_id=project_id,
        filename=slug,
        frontmatter=merged_front,
        body=body.strip(),
    )
    logger.info("Wrote BMAD artifact %s", full_path)

    # Mirror the bmad-generate-project-context output to a stable, glob-discoverable
    # path so each agent's `persistent_facts = ["file:{project-root}/**/project-context.md"]`
    # actually resolves the file the next time `load_bmad_agent()` runs.
    if skill == "bmad-generate-project-context" or slug == "project-context":
        try:
            stable = _project_dir(project_id, phase=phase) / "project-context.md"
            stable.write_text(text, encoding="utf-8")
            logger.info("Mirrored project-context.md to stable path %s", stable)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to mirror project-context.md: %s", exc)

    return artifact


def read_artifact(path: str | Path) -> Artifact:
    """Read an artifact file by absolute path."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Artifact not found: {p}")
    front, body = _parse_artifact(p)
    return Artifact(
        path=p,
        agent_code=front.get("agent", ""),
        skill=front.get("skill", ""),
        project_id=front.get("project_id", ""),
        filename=front.get("filename", p.stem),
        frontmatter=front,
        body=body.strip(),
    )


def list_artifacts(
    project_id: str,
    *,
    agent_code: str | None = None,
    phase: str = "planning",
) -> list[Artifact]:
    """List artifacts for a project, optionally filtered to one agent."""
    base = _project_dir(project_id, phase=phase)
    if not base.is_dir():
        return []
    results: list[Artifact] = []
    sub_dirs: Iterable[Path] = [base / agent_code] if agent_code else base.iterdir()
    for sub in sub_dirs:
        if not sub.is_dir():
            continue
        for md in sorted(sub.glob("*.md")):
            try:
                results.append(read_artifact(md))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping unreadable artifact %s: %s", md, exc)
    return results


def read_latest(project_id: str, agent_code: str, filename: str, *, phase: str = "planning") -> Artifact | None:
    """Read the most recent artifact for (agent_code, filename slug)."""
    dir_path = _agent_dir(project_id, agent_code, phase=phase)
    index_path = dir_path / "latest.json"
    if not index_path.is_file():
        return None
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    rel = index.get(_slug(filename))
    if not rel:
        return None
    full = dir_path / rel
    if not full.is_file():
        return None
    return read_artifact(full)


def collect_prior_context(
    project_id: str,
    *,
    upstream_agents: list[str],
    phase: str = "planning",
) -> list[dict[str, Any]]:
    """Return a list of artifact summaries for all upstream agents, in order.

    Used by a downstream node to assemble its user prompt with full upstream context.
    """
    out: list[dict[str, Any]] = []
    for agent_code in upstream_agents:
        for art in list_artifacts(project_id, agent_code=agent_code, phase=phase):
            out.append(art.to_summary())
    return out


def planning_root_for_project(project_id: str) -> Path:
    """Public accessor — returns `{planning_artifacts}/{project_id}/`."""
    p = _project_dir(project_id, phase="planning")
    p.mkdir(parents=True, exist_ok=True)
    return p


def implementation_root_for_project(project_id: str) -> Path:
    """Public accessor — returns `{implementation_artifacts}/{project_id}/`."""
    p = _project_dir(project_id, phase="implementation")
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── Internals ───────────────────────────────────────────────────────


def _update_latest_index(dir_path: Path, slug: str, path: Path) -> None:
    index_path = dir_path / "latest.json"
    try:
        existing = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else {}
    except Exception:  # noqa: BLE001
        existing = {}
    existing[slug] = path.name
    tmp = dir_path / ".latest.json.tmp"
    tmp.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, index_path)
