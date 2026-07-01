"""Helix Migration Engine — the deterministic, vendor-neutral core.

This package is the heart of the platform. It MUST stay pure: no FastAPI,
no Temporal, no database, and — critically — **no source/target vendor
imports**. Vendor-specific logic lives only in connector plugins.

The contract is: ``Any Source -> Canonical IR -> Any Target``. Source plugins
parse into the IR defined here; target plugins generate from it. Adding a new
system is therefore N+M adapters, never N*M conversions.

Sub-packages:
- ``ir``      canonical Intermediate Representation (types, transforms, model).
"""

from __future__ import annotations

from migration_engine.ir.version import IR_SCHEMA_VERSION

__all__ = ["IR_SCHEMA_VERSION"]
