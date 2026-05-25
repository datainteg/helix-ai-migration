"""Tests for the AST-based code-review fallback.

Intentionally dependency-light: imports only `agents.runtime.static_analysis`
(which is stdlib-only). Does NOT touch the BMAD loader, so it runs cleanly on
Python 3.10 where `tomllib` is unavailable.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repo root is importable without relying on the shared conftest.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agents.runtime.static_analysis import analyze_python_source  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────


def _findings(result: dict, category: str) -> list[dict]:
    return [f for f in result["structured_findings"] if f["category"] == category]


def _severities(result: dict) -> set[str]:
    return {f["severity"] for f in result["structured_findings"]}


# ── Tests ──────────────────────────────────────────────────────────────


def test_complexity_threshold_is_flagged():
    """A function with > 10 decision points should trigger a complexity finding."""
    # Build a function with 12 if-statements → complexity ~13.
    body = "\n".join(f"    if x == {i}: return {i}" for i in range(12))
    src = f'''"""mod"""

def complex_fn(x):
    """doc"""
{body}
    return 0
'''
    result = analyze_python_source(src, "complex.py")
    complexity = _findings(result, "complexity")
    assert len(complexity) >= 1, f"expected complexity finding, got {result['structured_findings']}"
    assert complexity[0]["severity"] in {"warn", "err"}
    assert "complex_fn" in complexity[0]["message"]


def test_nesting_depth_is_flagged():
    """Nesting depth > 4 should trigger a nesting finding."""
    src = '''"""mod"""

def deep(x):
    """doc"""
    if x:
        for i in x:
            while i:
                with open("/tmp/x") as f:
                    if f:
                        if i > 0:
                            return i
    return 0
'''
    result = analyze_python_source(src, "deep.py")
    nesting = _findings(result, "nesting")
    assert len(nesting) >= 1, f"expected nesting finding, got {result['structured_findings']}"
    assert nesting[0]["severity"] == "warn"
    assert "deep" in nesting[0]["message"]


def test_long_function_is_flagged():
    """A function body > 80 lines should trigger a long-function finding."""
    body = "\n".join(f"    a_{i} = {i}" for i in range(100))
    src = f'''"""mod"""

def too_long():
    """doc"""
{body}
'''
    result = analyze_python_source(src, "long.py")
    long_fn = _findings(result, "long-function")
    assert len(long_fn) == 1
    assert long_fn[0]["severity"] == "warn"
    assert "too_long" in long_fn[0]["message"]


def test_missing_docstring_flags_public_only():
    """Public funcs/classes without docstrings get info; underscore-prefixed are exempt."""
    src = '''"""mod"""

def public_no_doc(x):
    return x

def _private_no_doc(x):
    return x

class PublicNoDoc:
    pass

class _PrivateNoDoc:
    pass

def public_with_doc():
    """has one"""
    return 1
'''
    result = analyze_python_source(src, "docs.py")
    missing = _findings(result, "missing-docstring")
    names = [f["message"] for f in missing]

    # Public ones flagged.
    assert any("public_no_doc" in m for m in names), names
    assert any("PublicNoDoc" in m for m in names), names

    # Private ones NOT flagged.
    assert not any("_private_no_doc" in m for m in names), names
    assert not any("_PrivateNoDoc" in m for m in names), names

    # Documented public not flagged.
    assert not any("public_with_doc" in m for m in names), names

    for f in missing:
        assert f["severity"] == "info"


def test_aws_access_key_is_flagged_as_secret():
    """An AKIA-prefixed string literal → err-severity secret finding."""
    src = '''"""mod"""

AWS = "AKIAIOSFODNN7EXAMPLE"
'''
    result = analyze_python_source(src, "secrets.py")
    secrets = _findings(result, "secret")
    assert len(secrets) >= 1, f"expected secret finding, got {result['structured_findings']}"
    assert any(s["severity"] == "err" for s in secrets)
    assert result["risk_level"] == "HIGH"
    assert result["sign_off"] == "blocked"
    # blocking_issues must contain the secret string-form finding.
    assert any("secret" in b.lower() for b in result["blocking_issues"])


def test_bare_except_is_flagged():
    """`except:` and `except Exception:` both flagged as broad-except warns."""
    src = '''"""mod"""

def a():
    """doc"""
    try:
        pass
    except:
        pass

def b():
    """doc"""
    try:
        pass
    except Exception:
        pass
'''
    result = analyze_python_source(src, "exc.py")
    broad = _findings(result, "broad-except")
    assert len(broad) == 2, f"expected 2 broad-except findings, got {broad}"
    for f in broad:
        assert f["severity"] == "warn"


def test_non_python_source_returns_low_and_scans_secrets():
    """A .txt file should skip AST checks but still flag AKIA secrets."""
    src = "some random config\nAWS_KEY=AKIAIOSFODNN7EXAMPLE\nharmless line\n"
    result = analyze_python_source(src, "notes.txt")
    # Should NOT contain AST-derived categories.
    assert not _findings(result, "complexity")
    assert not _findings(result, "missing-docstring")
    # Should contain the secret finding.
    secrets = _findings(result, "secret")
    assert len(secrets) >= 1, f"expected secret in non-Python source, got {result}"
    # Even though risk is HIGH due to secret, summary should acknowledge non-Python path.
    assert "non-Python" in result["summary"] or "non-Python" in str(result)


def test_syntax_error_returns_single_warn_without_raising():
    """Unparseable Python should return one syntax warn finding (no exception)."""
    src = "def broken(:\n    return\n"
    result = analyze_python_source(src, "broken.py")
    syntax = _findings(result, "syntax")
    assert len(syntax) == 1
    assert syntax[0]["severity"] == "warn"
    # Output is still shaped correctly.
    assert "summary" in result
    assert "findings" in result
    assert "sign_off" in result


# ── Extra: cover eval/exec + TODO + risk-level transitions ────────────


def test_eval_exec_flagged():
    src = '''"""mod"""

def run(s):
    """doc"""
    eval(s)
    exec(s)
'''
    result = analyze_python_source(src, "danger.py")
    dangerous = _findings(result, "dangerous-call")
    assert len(dangerous) == 2
    assert {f["severity"] for f in dangerous} == {"warn"}


def test_todo_comments_flagged():
    src = '''"""mod"""

# TODO: refactor this
def x():
    """doc"""
    # FIXME urgent
    return 1
'''
    result = analyze_python_source(src, "todo.py")
    todos = _findings(result, "todo")
    assert len(todos) == 2
    assert {f["severity"] for f in todos} == {"info"}


def test_clean_code_is_low_risk_and_approved():
    src = '''"""Clean module."""

def add(a: int, b: int) -> int:
    """Sum two ints."""
    return a + b
'''
    result = analyze_python_source(src, "clean.py")
    assert result["risk_level"] == "LOW"
    assert result["sign_off"] == "approved"
    assert result["blocking_issues"] == []
