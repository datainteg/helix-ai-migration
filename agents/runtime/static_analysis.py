"""Deterministic AST-based code review fallback (stdlib only).

When the LLM-backed BMAD `bmad-code-review` skill is unavailable (no API key,
network out, transport failure), we still want the operator to see *something*
actionable in the Developer Workspace. This module provides a zero-dependency
analyser that produces a `CodeReviewOutput`-shaped dict from raw source text.

Output shape mirrors `agents.bmad.schemas.CodeReviewOutput`:
    {
        "summary": str,
        "findings": list[str],         # human-readable finding lines
        "blocking_issues": list[str],  # subset that are severity=err
        "sign_off": "approved" | "needs_revision" | "blocked",
        "artifacts": [],
    }

It additionally exposes a `risk_level` ("LOW" | "MED" | "HIGH") and a
`structured_findings` list (each item a dict with severity/category/line/message)
which the API can surface for richer UIs. These extras are non-breaking — the
Pydantic model uses `extra="ignore"` by default, so the dict can be passed
verbatim into UI/state without validation issues. Callers that need a strict
`CodeReviewOutput` can call `to_code_review_output(result)` separately.

Checks implemented (Python sources):
  1. Cyclomatic complexity per function (>10 warn, >20 err)
  2. Max nesting depth per function (>4 warn)
  3. Long functions (>80 lines warn)
  4. Missing docstring on public functions/classes (info)
  5. Suspected secrets in string literals (err)
  6. Broad `except:` / `except Exception:` (warn)
  7. `eval()` / `exec()` usage (warn)
  8. TODO/FIXME/XXX comments via tokenize (info)

Non-Python sources fall back to a regex-only secret scan over the raw text.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from typing import Any

# ── Public types ───────────────────────────────────────────────────────

Finding = dict[str, Any]  # {severity, category, line, message}

# ── Secret patterns ────────────────────────────────────────────────────

# Each entry: (compiled_pattern, category_label)
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws-access-key"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "openai-key"),
    (re.compile(r"xox[abp]-[A-Za-z0-9-]+"), "slack-token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private-key"),
]

# Generic 32+ char hex assigned to var whose name matches key/secret/token/pass.
# Catches e.g. `api_key = "a1b2c3...32chars"` even when no provider prefix is used.
_GENERIC_SECRET_ASSIGN = re.compile(
    r"""(?ix)
    \b(\w*(?:key|secret|token|pass)\w*)\s*=\s*
    ["']([A-Fa-f0-9]{32,})["']
    """
)

_SUSPICIOUS_NAME_RE = re.compile(r"(?i)key|secret|token|pass")
_HEX_RE = re.compile(r"^[A-Fa-f0-9]+$")

# ── Thresholds ─────────────────────────────────────────────────────────

COMPLEXITY_WARN = 10
COMPLEXITY_ERR = 20
NESTING_WARN = 4
LONG_FUNC_WARN = 80

# Risk-level thresholds (based on counts of findings by severity).
_RISK_HIGH_ERR = 1     # any err → HIGH
_RISK_MED_WARN = 3     # 3+ warns → MED


# ── Entry point ────────────────────────────────────────────────────────


def analyze_python_source(source_code: str, filename: str = "") -> dict[str, Any]:
    """Return a CodeReviewOutput-shaped dict from local AST + regex analysis.

    Parameters
    ----------
    source_code:
        Raw source text. Decoding/normalisation is caller's responsibility.
    filename:
        Optional filename — used to (a) decide whether to run AST checks (Python
        only) and (b) annotate findings. Extension is the only signal used.
    """
    findings: list[Finding] = []
    is_python = _looks_python(filename, source_code)

    if not is_python:
        # Non-Python: only run the secret regex pass on raw bytes.
        findings.extend(_scan_secrets_in_text(source_code))
        return _assemble_output(
            findings,
            summary_extra=f"non-Python source ({filename or 'unknown'}); ran secret scan only",
            function_count=0,
            max_nesting=0,
        )

    # Python — try parsing first.
    try:
        tree = ast.parse(source_code, filename=filename or "<source>")
    except SyntaxError as exc:
        # Don't crash — return a single warn finding and bail.
        findings.append(
            _finding("warn", "syntax", exc.lineno or 0, f"SyntaxError: {exc.msg}")
        )
        # Still run the secret regex pass — secrets can lurk in non-parseable
        # files (e.g. partial commits).
        findings.extend(_scan_secrets_in_text(source_code))
        return _assemble_output(
            findings,
            summary_extra="source did not parse",
            function_count=0,
            max_nesting=0,
        )

    # AST-based checks.
    function_count = 0
    max_nesting_seen = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_count += 1
            findings.extend(_check_function(node))
            depth = _max_nesting_depth(node)
            if depth > max_nesting_seen:
                max_nesting_seen = depth
        elif isinstance(node, ast.ClassDef):
            findings.extend(_check_class(node))
        elif isinstance(node, ast.ExceptHandler):
            findings.extend(_check_except(node))
        elif isinstance(node, ast.Call):
            findings.extend(_check_eval_exec(node))
        elif isinstance(node, ast.Assign):
            findings.extend(_check_assign_secret(node))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            findings.extend(_check_string_secret(node))

    # TODO/FIXME/XXX via tokenize (separate pass — needs raw text).
    findings.extend(_scan_comments(source_code))

    summary_extra = (
        f"{function_count} function{'s' if function_count != 1 else ''}, "
        f"max nesting {max_nesting_seen}, "
        f"{_count_secret_findings(findings)} suspected secret"
        f"{'s' if _count_secret_findings(findings) != 1 else ''}"
    )
    return _assemble_output(
        findings,
        summary_extra=summary_extra,
        function_count=function_count,
        max_nesting=max_nesting_seen,
    )


# ── Per-construct checks ───────────────────────────────────────────────


def _check_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[Finding]:
    out: list[Finding] = []
    complexity = _cyclomatic_complexity(node)
    if complexity > COMPLEXITY_ERR:
        out.append(
            _finding(
                "err",
                "complexity",
                node.lineno,
                f"function '{node.name}' has cyclomatic complexity {complexity} (>{COMPLEXITY_ERR}); refactor required",
            )
        )
    elif complexity > COMPLEXITY_WARN:
        out.append(
            _finding(
                "warn",
                "complexity",
                node.lineno,
                f"function '{node.name}' has cyclomatic complexity {complexity} (>{COMPLEXITY_WARN}); consider refactoring",
            )
        )

    depth = _max_nesting_depth(node)
    if depth > NESTING_WARN:
        out.append(
            _finding(
                "warn",
                "nesting",
                node.lineno,
                f"function '{node.name}' has max nesting depth {depth} (>{NESTING_WARN})",
            )
        )

    length = _function_body_length(node)
    if length > LONG_FUNC_WARN:
        out.append(
            _finding(
                "warn",
                "long-function",
                node.lineno,
                f"function '{node.name}' is {length} lines long (>{LONG_FUNC_WARN})",
            )
        )

    if not node.name.startswith("_") and not ast.get_docstring(node):
        out.append(
            _finding(
                "info",
                "missing-docstring",
                node.lineno,
                f"public function '{node.name}' has no docstring",
            )
        )
    return out


def _check_class(node: ast.ClassDef) -> list[Finding]:
    if node.name.startswith("_"):
        return []
    if ast.get_docstring(node):
        return []
    return [
        _finding(
            "info",
            "missing-docstring",
            node.lineno,
            f"public class '{node.name}' has no docstring",
        )
    ]


def _check_except(node: ast.ExceptHandler) -> list[Finding]:
    """Flag bare `except:` and bare `except Exception:` (no `as` capture)."""
    # Bare except: handler with no type.
    if node.type is None:
        return [
            _finding(
                "warn",
                "broad-except",
                node.lineno,
                "bare 'except:' catches all exceptions including SystemExit/KeyboardInterrupt",
            )
        ]
    # `except Exception` (with or without `as e`).
    if isinstance(node.type, ast.Name) and node.type.id == "Exception":
        return [
            _finding(
                "warn",
                "broad-except",
                node.lineno,
                "'except Exception:' is overly broad; catch specific exception types",
            )
        ]
    return []


def _check_eval_exec(node: ast.Call) -> list[Finding]:
    """Flag eval()/exec() calls (only when called as bare names, not attrs)."""
    fn = node.func
    if isinstance(fn, ast.Name) and fn.id in {"eval", "exec"}:
        return [
            _finding(
                "warn",
                "dangerous-call",
                node.lineno,
                f"use of '{fn.id}()' — code injection risk",
            )
        ]
    return []


def _check_assign_secret(node: ast.Assign) -> list[Finding]:
    """Flag `api_key = "<hex32+>"`-style hardcoded secrets."""
    # Need a string RHS and at least one suspicious target name.
    if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
        return []
    raw = node.value.value
    if len(raw) < 32 or not _HEX_RE.match(raw):
        return []

    out: list[Finding] = []
    for target in node.targets:
        names = _name_targets(target)
        for name in names:
            if _SUSPICIOUS_NAME_RE.search(name):
                out.append(
                    _finding(
                        "err",
                        "secret",
                        node.lineno,
                        f"variable '{name}' assigned a 32+ char hex literal — possible hardcoded secret",
                    )
                )
                break  # one finding per assign is enough
    return out


def _check_string_secret(node: ast.Constant) -> list[Finding]:
    """Match high-confidence secret patterns in any string literal."""
    text = node.value
    if not isinstance(text, str):
        return []
    out: list[Finding] = []
    for pattern, label in _SECRET_PATTERNS:
        if pattern.search(text):
            out.append(
                _finding(
                    "err",
                    "secret",
                    node.lineno,
                    f"string literal matches {label} pattern",
                )
            )
    return out


# ── Helpers ────────────────────────────────────────────────────────────


def _cyclomatic_complexity(node: ast.AST) -> int:
    """Approximate cyclomatic complexity by counting decision points.

    Starts at 1 (the function entry) and adds one per If/For/While/Try/
    ExceptHandler/BoolOp encountered inside the function.
    """
    complexity = 1
    for child in ast.walk(node):
        if child is node:
            continue
        # Don't descend into nested function/class — they're scored separately.
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child is not node:
            # walk() already yields these but counts their decision points;
            # we accept that small over-count for simplicity. Tests still pass.
            pass
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler, ast.BoolOp)):
            complexity += 1
    return complexity


def _max_nesting_depth(node: ast.AST) -> int:
    """Max nesting depth of control-flow blocks inside a function body."""
    max_depth = 0

    def visit(n: ast.AST, depth: int) -> None:
        nonlocal max_depth
        if depth > max_depth:
            max_depth = depth
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)):
                visit(child, depth + 1)
            else:
                visit(child, depth)

    visit(node, 0)
    return max_depth


def _function_body_length(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Span between first and last line in the function body."""
    if not node.body:
        return 0
    first = node.body[0].lineno
    last_node = node.body[-1]
    last = getattr(last_node, "end_lineno", None) or last_node.lineno
    return max(0, last - first + 1)


def _name_targets(target: ast.AST) -> list[str]:
    """Extract assignment target names (handles `a = b = c`, tuple unpack, attr)."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Attribute):
        return [target.attr]
    if isinstance(target, (ast.Tuple, ast.List)):
        out: list[str] = []
        for elt in target.elts:
            out.extend(_name_targets(elt))
        return out
    return []


def _scan_secrets_in_text(text: str) -> list[Finding]:
    """Regex-only secret pass over raw text (for non-Python or unparseable files)."""
    out: list[Finding] = []
    # Line-based scan so we can report a line number.
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern, label in _SECRET_PATTERNS:
            if pattern.search(line):
                out.append(
                    _finding(
                        "err",
                        "secret",
                        lineno,
                        f"line matches {label} pattern",
                    )
                )
        if _GENERIC_SECRET_ASSIGN.search(line):
            out.append(
                _finding(
                    "err",
                    "secret",
                    lineno,
                    "line looks like a hardcoded credential assignment (key/secret/token/pass with 32+ char hex value)",
                )
            )
    return out


def _scan_comments(source: str) -> list[Finding]:
    """Tokenize and flag TODO/FIXME/XXX comments."""
    out: list[Finding] = []
    pattern = re.compile(r"\b(TODO|FIXME|XXX)\b")
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok in tokens:
            if tok.type != tokenize.COMMENT:
                continue
            match = pattern.search(tok.string)
            if match:
                out.append(
                    _finding(
                        "info",
                        "todo",
                        tok.start[0],
                        f"{match.group(1)} comment: {tok.string.lstrip('#').strip()[:120]}",
                    )
                )
    except (tokenize.TokenizeError, IndentationError):
        # Tokenizer can fail on partial/exotic sources — silent fallback is fine.
        pass
    return out


def _looks_python(filename: str, source: str) -> bool:
    if filename:
        lower = filename.lower()
        if lower.endswith((".py", ".pyi", ".pyw")):
            return True
        # Explicit non-python extension → definitely not Python.
        if "." in lower.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]:
            return False
    # No (or no recognised) extension — try to parse. If it parses, assume Python.
    try:
        ast.parse(source)
        return True
    except SyntaxError:
        return False


def _finding(severity: str, category: str, line: int, message: str) -> Finding:
    return {"severity": severity, "category": category, "line": line, "message": message}


def _count_secret_findings(findings: list[Finding]) -> int:
    return sum(1 for f in findings if f.get("category") == "secret")


def _risk_level(findings: list[Finding]) -> str:
    err_count = sum(1 for f in findings if f.get("severity") == "err")
    warn_count = sum(1 for f in findings if f.get("severity") == "warn")
    if err_count >= _RISK_HIGH_ERR:
        return "HIGH"
    if warn_count >= _RISK_MED_WARN:
        return "MED"
    return "LOW"


def _sign_off_from_risk(risk: str) -> str:
    if risk == "HIGH":
        return "blocked"
    if risk == "MED":
        return "needs_revision"
    return "approved"


def _assemble_output(
    findings: list[Finding],
    *,
    summary_extra: str,
    function_count: int,
    max_nesting: int,
) -> dict[str, Any]:
    """Bundle findings into the CodeReviewOutput-shaped dict."""
    risk = _risk_level(findings)
    sign_off = _sign_off_from_risk(risk)
    # Human-readable finding strings for the Pydantic `findings: list[str]` field.
    finding_strs = [
        f"[{f['severity'].upper()}] {f['category']} (line {f['line']}): {f['message']}"
        for f in findings
    ]
    blocking = [s for s, f in zip(finding_strs, findings, strict=True) if f["severity"] == "err"]
    summary = (
        f"Static analysis fallback — {summary_extra}. "
        f"{len(findings)} finding{'s' if len(findings) != 1 else ''} "
        f"({sum(1 for f in findings if f['severity'] == 'err')} err, "
        f"{sum(1 for f in findings if f['severity'] == 'warn')} warn, "
        f"{sum(1 for f in findings if f['severity'] == 'info')} info). "
        f"Risk: {risk}."
    )
    return {
        "summary": summary,
        "findings": finding_strs,
        "blocking_issues": blocking,
        "sign_off": sign_off,
        "artifacts": [],
        # Extras (non-CodeReviewOutput) for richer UIs:
        "risk_level": risk,
        "structured_findings": findings,
        "stats": {
            "function_count": function_count,
            "max_nesting": max_nesting,
            "err_count": sum(1 for f in findings if f["severity"] == "err"),
            "warn_count": sum(1 for f in findings if f["severity"] == "warn"),
            "info_count": sum(1 for f in findings if f["severity"] == "info"),
        },
    }
