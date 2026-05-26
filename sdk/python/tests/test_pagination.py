"""Tests for pagination-envelope handling in the Python SDK.

These tests mock httpx responses so no real server is required.  They verify:
  - Envelope ``{items, total, limit, offset}`` is transparently unwrapped by
    every `.list()` method (back-compat guarantee).
  - The companion `.paginated()` helpers return the full envelope.
  - Bare-array responses (endpoints not yet converted) continue to work.
  - The ``_get_paginated()`` low-level helper synthesises a consistent envelope
    from a bare array.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from helix_sdk import Helix, PaginatedResponse
from helix_sdk.client import _unwrap, _as_paginated


# ---------------------------------------------------------------------------
# Unit tests for the helper functions
# ---------------------------------------------------------------------------

class TestUnwrap:
    def test_envelope_returns_items(self):
        data = {"items": [{"id": "1"}], "total": 1, "limit": 50, "offset": 0}
        assert _unwrap(data) == [{"id": "1"}]

    def test_bare_array_passthrough(self):
        data = [{"id": "1"}, {"id": "2"}]
        assert _unwrap(data) == data

    def test_empty_envelope(self):
        data = {"items": [], "total": 0, "limit": 50, "offset": 0}
        assert _unwrap(data) == []

    def test_empty_bare_array(self):
        assert _unwrap([]) == []


class TestAsPaginated:
    def test_envelope_shape_preserved(self):
        data = {"items": [{"id": "a"}], "total": 42, "limit": 10, "offset": 20}
        result = _as_paginated(data)
        assert result["items"] == [{"id": "a"}]
        assert result["total"] == 42
        assert result["limit"] == 10
        assert result["offset"] == 20

    def test_envelope_with_null_total(self):
        data = {"items": [{"id": "a"}], "total": None, "limit": 100, "offset": 0}
        result = _as_paginated(data)
        assert result["total"] is None

    def test_bare_array_synthesises_envelope(self):
        data = [{"id": "1"}, {"id": "2"}]
        result = _as_paginated(data)
        assert result["items"] == data
        assert result["total"] == 2
        assert result["limit"] == 2
        assert result["offset"] == 0

    def test_empty_bare_array(self):
        result = _as_paginated([])
        assert result["items"] == []
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# Helper to build a fake httpx.Response
# ---------------------------------------------------------------------------

def _mock_response(payload: object, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = json.dumps(payload)
    resp.json.return_value = payload
    return resp


# ---------------------------------------------------------------------------
# Integration-style tests: SDK methods with mocked httpx
# ---------------------------------------------------------------------------

def _make_helix() -> Helix:
    h = Helix("http://test.local", token="tok")
    return h


class TestWorkflowsList:
    """GET /agent-workflows — endpoint IS converted."""

    ENVELOPE = {"items": [{"workflow_id": "wf-1", "status": "running"}], "total": 1, "limit": 100, "offset": 0}
    BARE = [{"workflow_id": "wf-2", "status": "done"}]

    def test_list_unwraps_envelope(self):
        h = _make_helix()
        with patch("httpx.get", return_value=_mock_response(self.ENVELOPE)):
            result = h.workflows.list()
        assert isinstance(result, list)
        assert result == [{"workflow_id": "wf-1", "status": "running"}]

    def test_list_handles_bare_array(self):
        h = _make_helix()
        with patch("httpx.get", return_value=_mock_response(self.BARE)):
            result = h.workflows.list()
        assert result == self.BARE

    def test_paginated_returns_envelope(self):
        h = _make_helix()
        with patch("httpx.get", return_value=_mock_response(self.ENVELOPE)):
            result = h.workflows.paginated()
        assert result["total"] == 1
        assert result["items"] == [{"workflow_id": "wf-1", "status": "running"}]

    def test_paginated_handles_bare_array(self):
        h = _make_helix()
        with patch("httpx.get", return_value=_mock_response(self.BARE)):
            result = h.workflows.paginated()
        assert result["total"] == 1
        assert result["offset"] == 0

    def test_list_project_scoped_unwraps_envelope(self):
        h = _make_helix()
        with patch("httpx.get", return_value=_mock_response(self.ENVELOPE)):
            result = h.workflows.list(project_id="proj-1")
        assert isinstance(result, list)

    def test_paginated_project_scoped(self):
        h = _make_helix()
        with patch("httpx.get", return_value=_mock_response(self.ENVELOPE)):
            result = h.workflows.paginated(project_id="proj-1")
        assert isinstance(result, dict)
        assert "items" in result


class TestCutoversList:
    """GET /projects/{id}/cutovers — endpoint IS converted."""

    ENVELOPE = {"items": [{"id": "co-1", "state": "bulk"}], "total": 1, "limit": 50, "offset": 0}

    def test_list_unwraps_envelope(self):
        h = _make_helix()
        with patch("httpx.get", return_value=_mock_response(self.ENVELOPE)):
            result = h.cutovers.list("proj-1")
        assert result == [{"id": "co-1", "state": "bulk"}]

    def test_paginated_total(self):
        h = _make_helix()
        with patch("httpx.get", return_value=_mock_response(self.ENVELOPE)):
            result = h.cutovers.paginated("proj-1")
        assert result["total"] == 1
        assert result["limit"] == 50


class TestArtifactsList:
    """GET /projects/{id}/artifacts — endpoint IS converted."""

    ENVELOPE = {"items": [{"id": "art-1", "kind": "ddl"}], "total": 1, "limit": 50, "offset": 0}

    def test_list_for_project_unwraps(self):
        h = _make_helix()
        with patch("httpx.get", return_value=_mock_response(self.ENVELOPE)):
            result = h.artifacts.list_for_project("proj-1")
        assert result == [{"id": "art-1", "kind": "ddl"}]

    def test_list_for_project_paginated(self):
        h = _make_helix()
        with patch("httpx.get", return_value=_mock_response(self.ENVELOPE)):
            result = h.artifacts.list_for_project_paginated("proj-1")
        assert result["items"] == [{"id": "art-1", "kind": "ddl"}]
        assert result["offset"] == 0


class TestProjectsList:
    """GET /projects — NOT yet converted (bare array). Must still work."""

    BARE = [{"id": "p-1", "name": "My project", "status": "active"}]

    def test_list_bare_array(self):
        h = _make_helix()
        with patch("httpx.get", return_value=_mock_response(self.BARE)):
            result = h.projects.list()
        assert result == self.BARE

    def test_paginated_bare_array_synthesises(self):
        h = _make_helix()
        with patch("httpx.get", return_value=_mock_response(self.BARE)):
            result = h.projects.paginated()
        assert result["items"] == self.BARE
        assert result["total"] == 1


class TestGetPaginatedHelper:
    """Helix._get_paginated() low-level helper."""

    def test_wraps_envelope(self):
        h = _make_helix()
        envelope = {"items": [{"x": 1}], "total": 99, "limit": 10, "offset": 0}
        with patch("httpx.get", return_value=_mock_response(envelope)):
            result = h._get_paginated("/api/v1/anything")
        assert result["total"] == 99

    def test_wraps_bare_array(self):
        h = _make_helix()
        with patch("httpx.get", return_value=_mock_response([{"x": 1}, {"x": 2}])):
            result = h._get_paginated("/api/v1/anything")
        assert result["total"] == 2
        assert len(result["items"]) == 2


class TestPaginatedResponseType:
    """PaginatedResponse is exported and usable as a TypedDict."""

    def test_is_exported(self):
        from helix_sdk import PaginatedResponse  # noqa: F401

    def test_fields(self):
        pr: PaginatedResponse = {"items": [], "total": 0, "limit": 10, "offset": 0}  # type: ignore[misc]
        assert pr["items"] == []
