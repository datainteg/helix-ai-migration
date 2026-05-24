"""Test fixtures for the agents/ package.

`isolated_artifact_root` redirects all artifact writes to a tmp directory by:
  1. Copying `_bmad/` into a tmp project root (so the loader's config resolution
     finds the same TOML files).
  2. Pointing `HELIX_PROJECT_ROOT` at the tmp project root.
  3. Leaving `BMAD_METHOD_ROOT` pointing at the real vendored read-only tree
     (skills + customize.toml). We never write to that path.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture
def bmad_project_root() -> Path:
    return _REPO_ROOT


@pytest.fixture
def isolated_artifact_root(tmp_path, monkeypatch):
    """Redirect artifact writes to a tmp dir while reusing the real BMAD-METHOD source."""
    fake_root = tmp_path / "project"
    fake_root.mkdir()

    # Copy the installed `_bmad/` config tree into the tmp project root.
    shutil.copytree(_REPO_ROOT / "_bmad", fake_root / "_bmad")

    monkeypatch.setenv("HELIX_PROJECT_ROOT", str(fake_root))
    monkeypatch.setenv("BMAD_METHOD_ROOT", str(_REPO_ROOT / "agents" / "bmad" / "BMAD-METHOD"))

    from agents.runtime.bmad_loader import clear_cache

    clear_cache()
    yield fake_root
    clear_cache()
