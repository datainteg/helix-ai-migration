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


# SEC-011 — denylist of keys whose values must never reach YAML frontmatter
# (artifact files are surfaced via `/agent-workflows/{id}/artifact-content`
# and re-embedded in compliance PDFs). Anything in this set is dropped before
# `yaml.safe_dump` ever sees it. Also screened: any key starting with one of
# `_SECRET_KEY_PREFIXES` and any string value that looks secret-shaped.
_FRONTMATTER_DENYLIST: frozenset[str] = frozenset({
    # LLM transport — these are the ones SEC-011 specifically called out
    "api_key",
    "base_url",
    "endpoint",
    "endpoint_url",
    "azure_endpoint",
    "Authorization",
    "authorization",
    "bearer",
    "Bearer",
    # Cloud / vendor long-lived credentials
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_session_token",
    "service_account_json",
    "gcp_service_account_json",
    "client_secret",
    "azure_client_secret",
    "private_key",
    "passphrase",
    "password",
    "credentials",
    "credential",
})

_SECRET_KEY_PREFIXES: tuple[str, ...] = ("secret_", "password_", "token_", "apikey_")

# Value-shape heuristics: drop strings that look like live credentials even
# if the *key* slipped past the denylist (defence in depth — the LLM's own
# output can put a secret in any key it likes).
_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^sk-[A-Za-z0-9_-]{20,}$"),               # OpenAI / Anthropic
    re.compile(r"^sk-ant-[A-Za-z0-9_-]{20,}$"),           # Anthropic
    re.compile(r"^org-[A-Za-z0-9]{12,}$"),                # OpenAI organization id (M-003)
    re.compile(r"^xox[baprs]-[A-Za-z0-9-]{10,}$"),        # Slack
    re.compile(r"^AKIA[0-9A-Z]{12,}$"),                   # AWS access key ID
    re.compile(r"^ASIA[0-9A-Z]{12,}$"),                   # AWS STS key ID
    re.compile(r"^ghp_[A-Za-z0-9]{30,}$"),                # GitHub PAT
    re.compile(r"^gho_[A-Za-z0-9]{30,}$"),                # GitHub OAuth
    re.compile(r"^[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}$"),  # JWT
    re.compile(r"^Bearer\s+[A-Za-z0-9._-]{20,}$", re.IGNORECASE),
)

# M-003: lowered from 16 → 12 so shorter-but-still-credential tokens (e.g.
# OpenAI ``org-`` ids, 12-char AWS key suffixes) are screened by the
# value-shape heuristics below. Anything shorter than the smallest credential
# pattern can't match anyway, so this only widens, never narrows, coverage.
_MIN_SECRET_VALUE_LEN = 12

_REDACTED_SENTINEL = "[REDACTED]"


def _key_is_denied(key: str) -> bool:
    if not isinstance(key, str):
        return False
    if key in _FRONTMATTER_DENYLIST:
        return True
    low = key.lower()
    return any(low.startswith(p) for p in _SECRET_KEY_PREFIXES)


def _value_looks_secret(value: Any) -> bool:
    """True iff `value` is a string matching one of our secret-shape regexes."""
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if len(stripped) < _MIN_SECRET_VALUE_LEN:
        return False
    return any(pat.match(stripped) for pat in _SECRET_VALUE_PATTERNS)


def _safe_frontmatter(value: Any) -> Any:
    """SEC-011 — recursive scrubber for any dict-like frontmatter payload.

    - Drops every key in `_FRONTMATTER_DENYLIST` or matching a sensitive prefix.
    - Replaces any leaf string that matches a secret-shape regex with `[REDACTED]`.
    - Recurses through nested dicts + lists.
    - Returns a new structure; the input is not mutated.

    Used by `write_artifact` (and re-used by `compliance.py`) so a single
    filter governs every path that can leak a credential into an artifact
    file or a downloadable PDF.
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if _key_is_denied(k):
                # L-007: surface which keys the scrubber drops so operators
                # debugging "my provenance field vanished from the artifact"
                # can see it was a denylist hit, not a silent data-loss bug.
                logger.info("Frontmatter key %r dropped by secret scrubber (denied key)", k)
                continue
            out[k] = _safe_frontmatter(v)
        return out
    if isinstance(value, list):
        return [_safe_frontmatter(item) for item in value]
    if _value_looks_secret(value):
        return _REDACTED_SENTINEL
    return value


def _dump_frontmatter(frontmatter: dict[str, Any]) -> str:
    """Minimal YAML-like frontmatter serializer (JSON-safe, no external dep)."""
    import yaml

    return yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()


# Public alias — `compliance.py` and any future PDF/CSV exporter should call
# this on artifact metadata BEFORE embedding it into customer-downloadable
# bytes. Keeps the denylist + value-regex in one place.
def safe_frontmatter(value: Any) -> Any:  # noqa: D401 — re-export wrapper
    """Public alias for the secret-scrubbing helper (see `_safe_frontmatter`)."""
    return _safe_frontmatter(value)


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

    # SEC-011 — strip secrets before YAML serialisation. Artifact files are
    # surfaced via `/agent-workflows/{id}/artifact-content` and re-embedded
    # in compliance PDFs; any LLM-supplied or provenance-supplied credential
    # in here would leak verbatim. `_safe_frontmatter` is idempotent.
    safe_front = _safe_frontmatter(merged_front)

    text = f"---\n{_dump_frontmatter(safe_front)}\n---\n\n{body.strip()}\n"

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
        # SEC-011: hand the caller the same scrubbed dict that hit disk so
        # downstream consumers (e.g. workflow_service that mirrors metadata
        # into the WorkflowRun row) can't observe secrets either.
        frontmatter=safe_front,
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
