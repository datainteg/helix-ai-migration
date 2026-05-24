"""Generic JSON-extraction utility for LLM outputs.

Kept minimal on purpose. The BMAD-aligned execution path lives in
`agents.runtime.bmad_executor` and parses YAML frontmatter directly via
`yaml.safe_load`. This module exists only for the httpx LLM transport
(`agents.runtime.llm_client`) which needs to recover a JSON object from
free-form provider responses.
"""

from __future__ import annotations

import re

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def safe_extract_json(raw_text: str) -> str | None:
    """Extract a JSON string from raw text.

    Tries in order:
    1. Fenced ```json ... ``` block (or ``` ... ``` of any language)
    2. Raw { ... } JSON object
    3. Raw [ ... ] JSON array

    Returns the extracted JSON string or None when nothing matches.
    """
    if not raw_text or not raw_text.strip():
        return None

    match = _FENCED_JSON_RE.search(raw_text)
    if match:
        return match.group(1).strip()

    match = _JSON_OBJECT_RE.search(raw_text)
    if match:
        return match.group(0).strip()

    match = _JSON_ARRAY_RE.search(raw_text)
    if match:
        return match.group(0).strip()

    return None
