"""IBM DB2 native type -> canonical type mapping (source side).

Maps DB2 catalog type descriptors (as found in ``SYSCAT.COLUMNS`` /
``INFORMATION_SCHEMA``) into the engine's ``CanonicalType``. Anything unknown
becomes ``CanonicalType.unknown(...)`` carrying the raw DB2 type, so it surfaces
as manual effort rather than a silent wrong guess.

For DB2, the catalog stores DECIMAL precision in ``LENGTH`` and scale in
``SCALE``; TIMESTAMP fractional-seconds precision is stored in ``SCALE``.
"""

from __future__ import annotations

from typing import Optional

from migration_engine.ir.types import CanonicalType

_DECIMAL = {"DECIMAL", "NUMERIC", "DEC", "NUM"}
_FIXED_STR = {"CHARACTER", "CHAR", "GRAPHIC"}
_VAR_STR = {"VARCHAR", "CHARACTER VARYING", "CHAR VARYING", "VARGRAPHIC", "LONG VARCHAR"}
_LOB_STR = {"CLOB", "DBCLOB", "LONG VARGRAPHIC"}
_NATIONAL = {"GRAPHIC", "VARGRAPHIC", "DBCLOB", "LONG VARGRAPHIC"}


def parse_db2_type(
    type_name: str,
    *,
    length: Optional[int] = None,
    scale: Optional[int] = None,
    nullable: bool = True,
) -> CanonicalType:
    """Translate a DB2 type descriptor into a ``CanonicalType``."""
    raw = type_name
    name = " ".join(type_name.strip().upper().split())

    if name in _DECIMAL:
        return CanonicalType.decimal(length if length is not None else 5, scale or 0, nullable=nullable)
    if name == "SMALLINT":
        return CanonicalType.integer(16, nullable=nullable)
    if name in ("INTEGER", "INT"):
        return CanonicalType.integer(32, nullable=nullable)
    if name == "BIGINT":
        return CanonicalType.integer(64, nullable=nullable)
    if name == "REAL":
        return CanonicalType.floating(32, nullable=nullable)
    if name in ("DOUBLE", "DOUBLE PRECISION", "FLOAT"):
        return CanonicalType.floating(64, nullable=nullable)
    if name == "DECFLOAT":
        t = CanonicalType.floating(64, nullable=nullable)
        return _with_raw(t, raw)
    if name in ("BOOLEAN", "BOOL"):
        return CanonicalType.boolean(nullable=nullable)
    if name in _FIXED_STR:
        return _string(length, fixed=True, nullable=nullable, national=name in _NATIONAL)
    if name in _VAR_STR:
        return _string(length, fixed=False, nullable=nullable, national=name in _NATIONAL)
    if name in _LOB_STR:
        return _string(None, fixed=False, nullable=nullable, national=name in _NATIONAL, lob=True)
    if name == "BLOB":
        return CanonicalType.binary(None, nullable=nullable)
    if name == "BINARY":
        return CanonicalType.binary(length, fixed=True, nullable=nullable)
    if name == "VARBINARY":
        return CanonicalType.binary(length, nullable=nullable)
    if name == "DATE":
        return CanonicalType.date(nullable=nullable)
    if name == "TIME":
        return CanonicalType.time(nullable=nullable)
    if name.startswith("TIMESTAMP") and "TIME ZONE" in name:
        return CanonicalType.timestamp(precision=scale, with_timezone=True, nullable=nullable)
    if name in ("TIMESTAMP", "TIMESTMP"):
        return CanonicalType.timestamp(precision=scale, nullable=nullable)
    if name == "XML":
        t = CanonicalType(kind=_xml_kind(), nullable=nullable)
        return t
    return CanonicalType.unknown(raw, nullable=nullable)


def _string(
    length: Optional[int], *, fixed: bool, nullable: bool, national: bool = False, lob: bool = False
) -> CanonicalType:
    t = CanonicalType.string(length, fixed=fixed, nullable=nullable)
    meta = {}
    if national:
        meta["national"] = True
    if lob:
        meta["lob"] = True
    if meta:
        t.metadata.update(meta)
    return t


def _with_raw(t: CanonicalType, raw: str) -> CanonicalType:
    t.metadata["db2_type"] = raw
    return t


def _xml_kind():
    from migration_engine.ir.types import TypeKind

    return TypeKind.XML
