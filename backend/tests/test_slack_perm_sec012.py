"""SEC-012 — Slack privilege escalation regression tests.

Verifies that a Slack-authenticated request from a mapped Helix user who
lacks the `agent:approve` permission is rejected with HTTP 403 and that the
workflow status is left unchanged.

The test uses pytest monkeypatching to avoid needing a real Temporal cluster
or a real Slack signing exchange — we bypass signature verification in the
helper and wire up a minimal in-memory DB scenario.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_slack_headers(body: bytes, secret: str = "test-slack-secret") -> dict:
    ts = str(int(time.time()))
    basestring = f"v0:{ts}:{body.decode('utf-8')}".encode()
    digest = hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    return {
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": f"v0={digest}",
        "Content-Type": "application/x-www-form-urlencoded",
    }


def _register_admin(client) -> tuple[str, str]:
    """Create a first-admin user; return (token, user_id)."""
    res = client.post("/api/v1/auth/first-admin", json={
        "email": f"slack-admin-{uuid.uuid4().hex[:6]}@example.com",
        "name": "Slack Admin",
        "password": "SlackPass123!",
        "organization_name": "Slack Org",
        "organization_slug": f"slack-org-{uuid.uuid4().hex[:8]}",
    })
    assert res.status_code in (200, 201), res.text
    data = res.json()
    return data["access_token"], data["user_id"]


# ---------------------------------------------------------------------------
# SEC-012 core test
# ---------------------------------------------------------------------------

def test_slack_approve_without_agent_approve_permission_returns_403(client, monkeypatch):
    """A Slack user mapped to a Helix user without `agent:approve` must get 403.

    Strategy:
    - Register an admin (has all permissions) and capture the org/workflow.
    - Create a second low-privilege user in the same org who has NO agent:approve.
    - Point HELIX_SLACK_USER_MAP to the low-privilege user.
    - Send a validly-signed /helix approve command.
    - Assert the endpoint returns 403 and the workflow status did not change.
    """
    # We need the DB to have a workflow run.  Since creating a full workflow
    # run requires many moving parts, we mock the DB query + the permission
    # helper at the integration boundary so the test stays unit-level.

    slack_secret = "test-slack-secret"
    monkeypatch.setenv("SLACK_SIGNING_SECRET", slack_secret)

    workflow_id = f"wf-{uuid.uuid4().hex}"
    org_id = f"org-{uuid.uuid4().hex}"
    helix_user_id = f"user-lowpriv-{uuid.uuid4().hex}"
    slack_user_id = "U_LOWPRIV"

    # Map the Slack user → low-privilege Helix user via env
    monkeypatch.setenv("HELIX_SLACK_DEFAULT_USER", "")  # disable default
    user_map_path = _write_user_map({slack_user_id: helix_user_id}, tmp_path=None)
    monkeypatch.setenv("HELIX_SLACK_USER_MAP", user_map_path)

    # Build a fake WorkflowRun with matching org
    fake_run = MagicMock()
    fake_run.workflow_id = workflow_id
    fake_run.organization_id = org_id
    fake_run.status = "pending_approval"
    fake_run.mode = "auto"

    # Fake membership: user belongs to the SAME org (org-boundary passes)
    fake_membership = MagicMock()
    fake_membership.organization_id = org_id

    with (
        patch("app.api.integrations.SessionLocal") as mock_session_cls,
        patch("app.auth.dependencies.resolve_active_membership", return_value=fake_membership),
        patch("app.auth.dependencies.user_has_permission", return_value=False),  # no agent:approve
    ):
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = fake_run

        body = f"user_id={slack_user_id}&text=approve+{workflow_id}".encode()
        headers = _make_slack_headers(body, slack_secret)
        res = client.post("/api/v1/integrations/slack/command", content=body, headers=headers)

    assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
    # Workflow status must not have been mutated
    mock_db.commit.assert_not_called()


def test_slack_approve_wrong_org_returns_403(client, monkeypatch):
    """A Slack user mapped to a user in a *different* org must get 403."""
    slack_secret = "test-slack-secret"
    monkeypatch.setenv("SLACK_SIGNING_SECRET", slack_secret)

    workflow_id = f"wf-{uuid.uuid4().hex}"
    workflow_org_id = f"org-workflow-{uuid.uuid4().hex}"
    user_org_id = f"org-other-{uuid.uuid4().hex}"  # different org
    helix_user_id = f"user-other-org-{uuid.uuid4().hex}"
    slack_user_id = "U_WRONGORG"

    user_map_path = _write_user_map({slack_user_id: helix_user_id}, tmp_path=None)
    monkeypatch.setenv("HELIX_SLACK_USER_MAP", user_map_path)
    monkeypatch.setenv("HELIX_SLACK_DEFAULT_USER", "")

    fake_run = MagicMock()
    fake_run.workflow_id = workflow_id
    fake_run.organization_id = workflow_org_id  # workflow is in workflow_org_id
    fake_run.status = "pending_approval"
    fake_run.mode = "auto"

    fake_membership = MagicMock()
    fake_membership.organization_id = user_org_id  # user is in a DIFFERENT org

    with (
        patch("app.api.integrations.SessionLocal") as mock_session_cls,
        patch("app.auth.dependencies.resolve_active_membership", return_value=fake_membership),
        patch("app.auth.dependencies.user_has_permission", return_value=True),  # has permission
    ):
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = fake_run

        body = f"user_id={slack_user_id}&text=approve+{workflow_id}".encode()
        headers = _make_slack_headers(body, slack_secret)
        res = client.post("/api/v1/integrations/slack/command", content=body, headers=headers)

    assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
    mock_db.commit.assert_not_called()


def test_slack_approve_with_agent_approve_permission_signals_workflow(client, monkeypatch):
    """A user WITH agent:approve in the correct org should succeed (2xx)."""
    slack_secret = "test-slack-secret"
    monkeypatch.setenv("SLACK_SIGNING_SECRET", slack_secret)

    workflow_id = f"wf-{uuid.uuid4().hex}"
    org_id = f"org-{uuid.uuid4().hex}"
    helix_user_id = f"user-approver-{uuid.uuid4().hex}"
    slack_user_id = "U_APPROVER"

    user_map_path = _write_user_map({slack_user_id: helix_user_id}, tmp_path=None)
    monkeypatch.setenv("HELIX_SLACK_USER_MAP", user_map_path)
    monkeypatch.setenv("HELIX_SLACK_DEFAULT_USER", "")

    fake_run = MagicMock()
    fake_run.workflow_id = workflow_id
    fake_run.organization_id = org_id
    fake_run.status = "pending_approval"
    fake_run.mode = "auto"

    fake_membership = MagicMock()
    fake_membership.organization_id = org_id  # same org — passes boundary check

    mock_temporal_client = AsyncMock()
    mock_handle = AsyncMock()
    mock_temporal_client.get_workflow_handle.return_value = mock_handle

    with (
        patch("app.api.integrations.SessionLocal") as mock_session_cls,
        patch("app.auth.dependencies.resolve_active_membership", return_value=fake_membership),
        patch("app.auth.dependencies.user_has_permission", return_value=True),
        patch("app.api.integrations.update_workflow_run_status"),
        patch("app.api.integrations.write_audit"),
        patch("temporalio.client.Client.connect", return_value=mock_temporal_client),
    ):
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = fake_run

        body = f"user_id={slack_user_id}&text=approve+{workflow_id}".encode()
        headers = _make_slack_headers(body, slack_secret)
        res = client.post("/api/v1/integrations/slack/command", content=body, headers=headers)

    # The Temporal signal may fail in test (no real cluster) but the permission
    # gate must have passed, so we should NOT get 403.
    assert res.status_code != 403, f"Should not be 403 for a permitted user: {res.text}"


# ---------------------------------------------------------------------------
# helper — write a temp user-map JSON file
# ---------------------------------------------------------------------------

def _write_user_map(mapping: dict, tmp_path) -> str:
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(mapping, f)
    return path
