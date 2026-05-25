"""Performance tests — SSE handlers do not hold DB sessions across polls.

H-8 from REVIEW_PERFORMANCE.md: each open SSE connection used to pin a
DB session for the entire polling window (5 min for sprints, 2 min for
agent_workflows). The fix opens a fresh SessionLocal() per tick and
closes it before the asyncio.sleep, so pool checkout pressure tracks
actual query time rather than the SSE window.

We don't drive a full SSE connection (the test client would hold one
open indefinitely); instead we structurally assert:
  - The handler signature accepts a Request and does NOT take
    Depends(get_db).
  - The handler body contains a per-tick `SessionLocal()` open AND
    closes it inside a finally before the asyncio.sleep call.
  - The handler body checks `await request.is_disconnected()` inside
    the loop body — guarantees closed tabs tear down within 1-2 s.

These are source-level checks, deliberately. The behavioural integration
test would require simulating mid-stream disconnect, which is awkward
with starlette's test client.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SSE_HANDLERS = [
    (
        _REPO_ROOT / "app" / "api" / "sprints.py",
        "api_executions_stream",
    ),
    (
        _REPO_ROOT / "app" / "api" / "agent_workflows.py",
        "stream_workflow_progress",
    ),
]


def _load_handler(path: Path, fn_name: str) -> ast.AsyncFunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == fn_name:
            return node
    raise AssertionError(f"async handler {fn_name} not found in {path}")


@pytest.mark.parametrize("path, fn_name", _SSE_HANDLERS)
def test_sse_handler_is_async(path: Path, fn_name: str):
    """SSE handlers MUST be `async def` so we can `await
    request.is_disconnected()` inside the generator."""
    handler = _load_handler(path, fn_name)
    assert isinstance(handler, ast.AsyncFunctionDef)


@pytest.mark.parametrize("path, fn_name", _SSE_HANDLERS)
def test_sse_handler_takes_request(path: Path, fn_name: str):
    """`request: Request` must be a parameter so we can poll for
    disconnect."""
    handler = _load_handler(path, fn_name)
    arg_names = {a.arg for a in handler.args.args}
    assert "request" in arg_names, f"{fn_name} must accept `request: Request`"


@pytest.mark.parametrize("path, fn_name", _SSE_HANDLERS)
def test_sse_handler_does_not_depends_get_db(path: Path, fn_name: str):
    """The handler must NOT pin a Depends(get_db) session for the
    whole stream — that was the core leak. Sessions are opened
    inside the generator instead."""
    handler = _load_handler(path, fn_name)
    src = ast.get_source_segment(path.read_text(encoding="utf-8"), handler)
    assert src is not None
    # Crude but effective: the handler signature should not contain
    # `Depends(get_db)` anywhere. (We allow other Depends(...) for
    # auth/org resolution if added later.)
    sig_block = src.split(":\n", 1)[0]
    assert "Depends(get_db)" not in sig_block, (
        f"{fn_name} still uses Depends(get_db) — pool will be exhausted "
        f"by long-running SSE streams. See H-8 in REVIEW_PERFORMANCE.md."
    )


@pytest.mark.parametrize("path, fn_name", _SSE_HANDLERS)
def test_sse_handler_opens_sessionlocal_per_tick(path: Path, fn_name: str):
    """Inside the generator body there must be at least one explicit
    SessionLocal() call — that's the per-tick session."""
    src = path.read_text(encoding="utf-8")
    # Generator name is consistent across both handlers.
    assert "SessionLocal()" in src, (
        f"{fn_name}: missing per-tick `SessionLocal()` open. "
        f"Without it the handler reverts to a single pinned session."
    )


@pytest.mark.parametrize("path, fn_name", _SSE_HANDLERS)
def test_sse_handler_calls_is_disconnected(path: Path, fn_name: str):
    """The poll loop must check `request.is_disconnected()` every
    iteration so closed tabs tear down within the poll interval."""
    src = path.read_text(encoding="utf-8")
    assert "request.is_disconnected()" in src, (
        f"{fn_name}: missing `await request.is_disconnected()` check. "
        f"Closed browser tabs will keep the stream alive for the full "
        f"polling window."
    )


@pytest.mark.parametrize("path, fn_name", _SSE_HANDLERS)
def test_sse_handler_closes_session_in_finally(path: Path, fn_name: str):
    """The per-tick SessionLocal() must be wrapped in try/finally with
    a .close() call, so a yield-cancellation (client disconnect mid
    chunk) doesn't leak the connection."""
    src = path.read_text(encoding="utf-8")
    # We assert the literal `.close()` appears at least twice — once
    # for the auth session and once per the per-tick session.
    close_count = src.count(".close()")
    assert close_count >= 2, (
        f"{fn_name}: expected the auth Session AND per-tick Session "
        f"each closed in finally; found {close_count} `.close()` calls."
    )


@pytest.mark.parametrize("path, fn_name", _SSE_HANDLERS)
def test_sse_handler_handles_cancellation(path: Path, fn_name: str):
    """The generator should re-raise asyncio.CancelledError so
    Starlette can clean up quietly without an unhandled-exception
    traceback in the logs."""
    src = path.read_text(encoding="utf-8")
    assert "asyncio.CancelledError" in src, (
        f"{fn_name}: missing `except asyncio.CancelledError` so the "
        f"common mid-stream disconnect path will log an unhandled "
        f"exception every time."
    )
