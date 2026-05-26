"""SEC-018 — schema-snapshot JSON DoS regression tests.

Covers the three guard layers added to schema_drift.py:
  1. Byte-size cap (10 MB by default) → 413
  2. Nesting-depth cap (64 levels)    → 422
  3. Node-count cap (100 k nodes)     → 422

All tests exercise the public helpers directly as unit tests (fast, no DB)
plus one end-to-end integration test that sends a real oversized snapshot
through the API.
"""

from __future__ import annotations

import json
import uuid

import pytest

from app.api.schema_drift import (
    _SNAPSHOT_MAX_BYTES,
    _SNAPSHOT_MAX_DEPTH,
    _SNAPSHOT_MAX_NODES,
    _check_depth,
    _count_nodes,
    _validate_snapshot_json,
)
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

class TestCheckDepth:
    def test_flat_dict_ok(self):
        _check_depth({"a": 1, "b": [1, 2]})  # should not raise

    def test_depth_at_limit_ok(self):
        # Build a chain exactly at the limit; should pass.
        obj: dict = {}
        node = obj
        for _ in range(_SNAPSHOT_MAX_DEPTH - 1):
            node["child"] = {}
            node = node["child"]
        _check_depth(obj)  # no exception

    def test_depth_over_limit_raises_422(self):
        # One level deeper than the cap.
        obj: dict = {}
        node = obj
        for _ in range(_SNAPSHOT_MAX_DEPTH + 1):
            node["child"] = {}
            node = node["child"]
        with pytest.raises(HTTPException) as exc_info:
            _check_depth(obj)
        assert exc_info.value.status_code == 422

    def test_list_nesting_raises_422(self):
        # Deep nesting through lists.
        obj: list = []
        node = obj
        for _ in range(_SNAPSHOT_MAX_DEPTH + 5):
            inner: list = []
            node.append(inner)
            node = inner
        with pytest.raises(HTTPException) as exc_info:
            _check_depth(obj)
        assert exc_info.value.status_code == 422


class TestCountNodes:
    def test_small_object_ok(self):
        count: list[int] = [0]
        _count_nodes({"a": 1, "b": [1, 2, {"c": 3}]}, count)
        assert count[0] > 0

    def test_over_limit_raises_422(self):
        # Build a flat list of dicts that exceeds the node cap.
        big_list = [{"x": i} for i in range(_SNAPSHOT_MAX_NODES + 1)]
        count: list[int] = [0]
        with pytest.raises(HTTPException) as exc_info:
            _count_nodes(big_list, count)
        assert exc_info.value.status_code == 422


class TestValidateSnapshotJson:
    def test_valid_small_payload_ok(self):
        raw = json.dumps({"tables": [{"schema_name": "public", "table_name": "t", "columns": []}]})
        result = _validate_snapshot_json(raw)
        assert "tables" in result

    def test_oversized_payload_raises_413(self, monkeypatch):
        # Temporarily lower the cap so we don't actually allocate 10 MB in tests.
        monkeypatch.setattr("app.api.schema_drift._SNAPSHOT_MAX_BYTES", 100)
        raw = "x" * 200  # 200 bytes > 100
        with pytest.raises(HTTPException) as exc_info:
            _validate_snapshot_json(raw)
        assert exc_info.value.status_code == 413

    def test_deeply_nested_payload_raises_422(self):
        # 200-level deep dict — well above the 64-level cap.
        obj: dict = {}
        node = obj
        for _ in range(200):
            node["child"] = {}
            node = node["child"]
        raw = json.dumps(obj)
        with pytest.raises(HTTPException) as exc_info:
            _validate_snapshot_json(raw)
        assert exc_info.value.status_code == 422

    def test_node_count_bomb_raises_422(self, monkeypatch):
        # Lower the cap so the test is fast.
        monkeypatch.setattr("app.api.schema_drift._SNAPSHOT_MAX_NODES", 50)
        # Build a payload with many nodes.
        big = {"tables": [{"schema_name": "s", "table_name": f"t{i}", "columns": []} for i in range(100)]}
        raw = json.dumps(big)
        with pytest.raises(HTTPException) as exc_info:
            _validate_snapshot_json(raw)
        assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# Integration / end-to-end tests through the API
# ---------------------------------------------------------------------------

def _admin_token(client) -> tuple[str, str]:
    """Register a first-admin; return (token, project_id)."""
    slug = f"dos-{uuid.uuid4().hex[:8]}"
    res = client.post("/api/v1/auth/first-admin", json={
        "email": f"dos+{slug}@example.com",
        "name": "DoS Admin",
        "password": "DosPass123!",
        "organization_name": "DoS Org",
        "organization_slug": slug,
    })
    assert res.status_code in (200, 201), res.text
    token = res.json()["access_token"]

    proj = client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "dos-test"},
    )
    pid = proj.json().get("id") if proj.status_code in (200, 201) else None
    return token, pid


def _post_snapshot(client, token, project_id, tables, *, source_ref="src"):
    return client.post(
        f"/api/v1/projects/{project_id}/sources/{source_ref}/schema-snapshots",
        headers={"Authorization": f"Bearer {token}"},
        json={"schemas": ["public"], "tables": tables},
    )


def test_snapshot_oversized_returns_413(client, monkeypatch):
    """An 11 MB snapshot (above the 10 MB cap) must be rejected with 413."""
    # Lower the cap for speed: set to 500 bytes for this test.
    monkeypatch.setattr("app.api.schema_drift._SNAPSHOT_MAX_BYTES", 500)

    token, pid = _admin_token(client)
    if not pid:
        pytest.skip("Could not create project")

    # Generate a payload bigger than 500 bytes.
    big_tables = [{"schema_name": "public", "table_name": f"table_{i}", "columns": [
        {"name": "col_a", "data_type": "varchar"},
        {"name": "col_b", "data_type": "int"},
    ]} for i in range(20)]  # ~1 KB

    res = _post_snapshot(client, token, pid, big_tables)
    assert res.status_code == 413, f"Expected 413 for oversized snapshot, got {res.status_code}: {res.text}"


def test_snapshot_deeply_nested_returns_422(client, monkeypatch):
    """A snapshot with 200-level deep nesting must be rejected with 422."""
    token, pid = _admin_token(client)
    if not pid:
        pytest.skip("Could not create project")

    # Build a table whose 'columns' value is a 200-deep nested dict instead
    # of the expected list — this is the adversarial depth-bomb.
    deep_obj: dict = {}
    node = deep_obj
    for _ in range(200):
        node["child"] = {}
        node = node["child"]

    # We send the nested object as the `tables` element to trigger the check.
    tables = [{"schema_name": "public", "table_name": "bomb", "columns": deep_obj}]
    res = _post_snapshot(client, token, pid, tables)
    assert res.status_code in (413, 422), (
        f"Expected 413/422 for deeply nested snapshot, got {res.status_code}: {res.text}"
    )


def test_snapshot_node_count_bomb_returns_422(client, monkeypatch):
    """A snapshot with > 100k nodes must be rejected with 422."""
    # Lower the cap for test speed.
    monkeypatch.setattr("app.api.schema_drift._SNAPSHOT_MAX_NODES", 100)

    token, pid = _admin_token(client)
    if not pid:
        pytest.skip("Could not create project")

    # 50 tables × 3 columns each = 150+ nodes (above cap of 100).
    tables = [
        {
            "schema_name": "public",
            "table_name": f"tbl_{i}",
            "columns": [
                {"name": "a", "data_type": "int"},
                {"name": "b", "data_type": "varchar"},
                {"name": "c", "data_type": "text"},
            ],
        }
        for i in range(50)
    ]
    res = _post_snapshot(client, token, pid, tables)
    assert res.status_code in (413, 422), (
        f"Expected 413/422 for node-count bomb, got {res.status_code}: {res.text}"
    )
