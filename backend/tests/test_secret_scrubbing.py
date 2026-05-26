"""SEC-011 — secret scrubbing in artifact frontmatter + compliance PDF.

Two layers under test:

  1. `agents.runtime.artifact_store.safe_frontmatter` — the recursive
     dict scrubber that strips denied keys and redacts secret-shaped values.

  2. `agents.runtime.artifact_store.write_artifact` — end-to-end test that
     a frontmatter dict containing `api_key` / `base_url` never lands on
     disk.

Compliance PDF coverage is in test_extra_config_encryption.py companion
test_compliance_pdf_no_api_key (uses the live ReportLab path).
"""

from __future__ import annotations

import importlib
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ── 1. safe_frontmatter — unit ────────────────────────────────────────


def test_safe_frontmatter_strips_api_key():
    from agents.runtime.artifact_store import safe_frontmatter
    cleaned = safe_frontmatter({
        "agent": "bmad-agent-dev",
        "api_key": "sk-ant-LIVE-KEY-DO-NOT-LEAK",
        "model": "claude-opus",
    })
    assert "api_key" not in cleaned
    assert cleaned["agent"] == "bmad-agent-dev"
    assert cleaned["model"] == "claude-opus"


def test_safe_frontmatter_strips_base_url():
    from agents.runtime.artifact_store import safe_frontmatter
    cleaned = safe_frontmatter({
        "agent": "bmad-agent-dev",
        "base_url": "https://api.anthropic.com",
    })
    assert "base_url" not in cleaned


def test_safe_frontmatter_strips_authorization_header():
    from agents.runtime.artifact_store import safe_frontmatter
    cleaned = safe_frontmatter({
        "Authorization": "Bearer sk-test-LEAK",
        "authorization": "Bearer sk-test-LEAK-2",
        "bearer": "sk-test-LEAK-3",
    })
    assert "Authorization" not in cleaned
    assert "authorization" not in cleaned
    assert "bearer" not in cleaned


def test_safe_frontmatter_strips_prefixed_secret_keys():
    from agents.runtime.artifact_store import safe_frontmatter
    cleaned = safe_frontmatter({
        "secret_key": "x",
        "password_hash": "y",
        "token_jwt": "z",
        "ok_field": "kept",
    })
    assert "secret_key" not in cleaned
    assert "password_hash" not in cleaned
    assert "token_jwt" not in cleaned
    assert cleaned["ok_field"] == "kept"


def test_safe_frontmatter_redacts_secret_shaped_values():
    from agents.runtime.artifact_store import safe_frontmatter
    cleaned = safe_frontmatter({
        "summary": "All good",
        "leaked_inline": "sk-ant-abcdefghijklmnopqrstuvwxyz0123456789ABCD",
        "leaked_aws": "AKIAABCDEFGHIJKLMNOP",
        "leaked_jwt": (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTYifQ."
            "abcdefghijklmnopqrstuvwxyz0123"
        ),
    })
    assert cleaned["summary"] == "All good"
    assert cleaned["leaked_inline"] == "[REDACTED]"
    assert cleaned["leaked_aws"] == "[REDACTED]"
    assert cleaned["leaked_jwt"] == "[REDACTED]"


def test_safe_frontmatter_recurses_into_nested_dicts_and_lists():
    from agents.runtime.artifact_store import safe_frontmatter
    cleaned = safe_frontmatter({
        "outer": {
            "api_key": "should-be-gone",
            "items": [
                {"api_key": "also-gone"},
                {"keep": "value"},
            ],
        }
    })
    assert "api_key" not in cleaned["outer"]
    assert "api_key" not in cleaned["outer"]["items"][0]
    assert cleaned["outer"]["items"][1] == {"keep": "value"}


def test_safe_frontmatter_idempotent():
    """Running the scrubber twice produces the same output."""
    from agents.runtime.artifact_store import safe_frontmatter
    payload = {"api_key": "x", "ok": "y"}
    once = safe_frontmatter(payload)
    twice = safe_frontmatter(once)
    assert once == twice


# ── 2. write_artifact end-to-end ───────────────────────────────────────


def test_write_artifact_strips_api_key_from_disk(tmp_path, monkeypatch):
    """write_artifact must never persist api_key/base_url into the YAML file."""
    # Redirect artifact storage to a tmpdir.
    import agents.runtime.artifact_store as store_mod

    fake_planning = tmp_path / "planning"
    fake_planning.mkdir()
    fake_implementation = tmp_path / "implementation"
    fake_implementation.mkdir()

    class _StubCfg:
        planning_artifacts = str(fake_planning)
        implementation_artifacts = str(fake_implementation)

    monkeypatch.setattr(store_mod, "load_bmad_config", lambda: _StubCfg())

    artifact = store_mod.write_artifact(
        project_id="proj-test",
        agent_code="bmad-agent-dev",
        skill="bmad-implement",
        filename="impl",
        body="# done",
        frontmatter={
            "api_key": "sk-ant-LIVE-KEY-DO-NOT-LEAK",
            "base_url": "https://api.anthropic.com",
            "Authorization": "Bearer should-not-survive",
            "summary": "OK",
            "provider_type": "anthropic",
            "model": "claude-opus",
            "correlation_id": "abc-123",
        },
    )

    # In-memory artifact dict must already be scrubbed.
    assert "api_key" not in artifact.frontmatter
    assert "base_url" not in artifact.frontmatter
    assert "Authorization" not in artifact.frontmatter
    assert artifact.frontmatter["provider_type"] == "anthropic"
    assert artifact.frontmatter["model"] == "claude-opus"

    # File on disk must not contain the secret bytes either.
    disk_bytes = artifact.path.read_bytes()
    assert b"sk-ant-LIVE-KEY-DO-NOT-LEAK" not in disk_bytes
    assert b"api_key" not in disk_bytes
    # base_url is also dropped (the original SEC-011 finding called this out).
    assert b"base_url" not in disk_bytes


# ── 3. Compliance scrub helper ────────────────────────────────────────


def test_compliance_scrub_text_redacts_secret_shaped_strings():
    """The PDF builder's text-scrubber must redact secret-shaped strings."""
    try:
        from app.api.compliance import _scrub_text
    except ImportError as exc:
        # Pre-existing local-env gaps (email-validator etc.) — module won't
        # import. The unit-level scrubber test above already pins the algorithm.
        pytest.skip(f"compliance module not importable in this env: {exc}")
    # Pure-secret string → REDACTED token.
    assert _scrub_text("sk-ant-abcdefghijklmnopqrstuvwxyz0123456789ABCD") == "[REDACTED]"
    # Plain audit action label → unchanged.
    assert _scrub_text("project.created") == "project.created"
    # None → empty string (avoids `None` rendering in PDFs).
    assert _scrub_text(None) == ""
