"""Canonical, vendor-neutral type system.

Source connectors map their native types *into* a ``CanonicalType``; target
connectors map *out* of it. Because the canonical type carries structured
parameters (precision, scale, length, timezone, nesting), the mapping is
deterministic — e.g. DB2 ``DECIMAL(10,2)`` -> canonical ``decimal(10,2)`` ->
Snowflake ``NUMBER(10,2)``.

Anything a source cannot be mapped to becomes ``TypeKind.UNKNOWN`` while
preserving ``raw_source_type`` so the Assessment engine can report it as manual
effort instead of silently guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TypeKind(str, Enum):
    """Logical, vendor-neutral type families."""

    BOOLEAN = "boolean"
    INTEGER = "integer"          # bit_width: 8 | 16 | 32 | 64
    DECIMAL = "decimal"          # precision, scale (exact numeric)
    FLOAT = "float"              # bit_width: 32 | 64 (approximate numeric)
    STRING = "string"            # length, fixed (CHAR vs VARCHAR)
    BINARY = "binary"            # length, fixed (BINARY vs VARBINARY)
    DATE = "date"
    TIME = "time"                # precision (fractional seconds)
    TIMESTAMP = "timestamp"      # precision, with_timezone
    INTERVAL = "interval"
    JSON = "json"
    XML = "xml"
    ARRAY = "array"              # element
    STRUCT = "struct"            # fields
    MAP = "map"                  # key, value
    VARIANT = "variant"          # semi-structured catch-all (e.g. Snowflake VARIANT)
    UNKNOWN = "unknown"          # unmapped; see raw_source_type


@dataclass(frozen=True)
class StructField:
    """A named field within a STRUCT type."""

    name: str
    type: "CanonicalType"


@dataclass
class CanonicalType:
    """A fully-parameterised canonical type.

    Only the parameters relevant to ``kind`` are populated; the rest stay None /
    default. ``raw_source_type`` preserves the original vendor type string for
    round-tripping and unsupported-feature reporting.
    """

    kind: TypeKind
    nullable: bool = True

    # numeric
    precision: Optional[int] = None
    scale: Optional[int] = None
    bit_width: Optional[int] = None

    # string / binary
    length: Optional[int] = None
    fixed: bool = False

    # temporal
    with_timezone: bool = False

    # nested
    element: Optional["CanonicalType"] = None
    key: Optional["CanonicalType"] = None
    value: Optional["CanonicalType"] = None
    fields: tuple[StructField, ...] = ()

    # provenance + extension
    raw_source_type: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    # ----- ergonomic constructors -------------------------------------------
    @classmethod
    def boolean(cls, *, nullable: bool = True) -> "CanonicalType":
        return cls(TypeKind.BOOLEAN, nullable=nullable)

    @classmethod
    def integer(cls, bit_width: int = 32, *, nullable: bool = True) -> "CanonicalType":
        return cls(TypeKind.INTEGER, bit_width=bit_width, nullable=nullable)

    @classmethod
    def decimal(
        cls, precision: int, scale: int = 0, *, nullable: bool = True
    ) -> "CanonicalType":
        return cls(TypeKind.DECIMAL, precision=precision, scale=scale, nullable=nullable)

    @classmethod
    def floating(cls, bit_width: int = 64, *, nullable: bool = True) -> "CanonicalType":
        return cls(TypeKind.FLOAT, bit_width=bit_width, nullable=nullable)

    @classmethod
    def string(
        cls, length: Optional[int] = None, *, fixed: bool = False, nullable: bool = True
    ) -> "CanonicalType":
        return cls(TypeKind.STRING, length=length, fixed=fixed, nullable=nullable)

    @classmethod
    def binary(
        cls, length: Optional[int] = None, *, fixed: bool = False, nullable: bool = True
    ) -> "CanonicalType":
        return cls(TypeKind.BINARY, length=length, fixed=fixed, nullable=nullable)

    @classmethod
    def date(cls, *, nullable: bool = True) -> "CanonicalType":
        return cls(TypeKind.DATE, nullable=nullable)

    @classmethod
    def time(cls, precision: Optional[int] = None, *, nullable: bool = True) -> "CanonicalType":
        return cls(TypeKind.TIME, precision=precision, nullable=nullable)

    @classmethod
    def timestamp(
        cls,
        precision: Optional[int] = None,
        *,
        with_timezone: bool = False,
        nullable: bool = True,
    ) -> "CanonicalType":
        return cls(
            TypeKind.TIMESTAMP,
            precision=precision,
            with_timezone=with_timezone,
            nullable=nullable,
        )

    @classmethod
    def json(cls, *, nullable: bool = True) -> "CanonicalType":
        return cls(TypeKind.JSON, nullable=nullable)

    @classmethod
    def variant(cls, *, nullable: bool = True) -> "CanonicalType":
        return cls(TypeKind.VARIANT, nullable=nullable)

    @classmethod
    def array(cls, element: "CanonicalType", *, nullable: bool = True) -> "CanonicalType":
        return cls(TypeKind.ARRAY, element=element, nullable=nullable)

    @classmethod
    def map_(
        cls, key: "CanonicalType", value: "CanonicalType", *, nullable: bool = True
    ) -> "CanonicalType":
        return cls(TypeKind.MAP, key=key, value=value, nullable=nullable)

    @classmethod
    def struct(cls, fields: tuple[StructField, ...], *, nullable: bool = True) -> "CanonicalType":
        return cls(TypeKind.STRUCT, fields=tuple(fields), nullable=nullable)

    @classmethod
    def unknown(cls, raw_source_type: str, *, nullable: bool = True) -> "CanonicalType":
        return cls(TypeKind.UNKNOWN, raw_source_type=raw_source_type, nullable=nullable)

    # ----- helpers ----------------------------------------------------------
    @property
    def is_unknown(self) -> bool:
        return self.kind is TypeKind.UNKNOWN

    @property
    def is_nested(self) -> bool:
        return self.kind in (TypeKind.ARRAY, TypeKind.STRUCT, TypeKind.MAP)

    def signature(self) -> str:
        """Stable, human-readable signature — handy for golden tests & docs."""
        k = self.kind
        if k is TypeKind.INTEGER:
            base = f"integer{self.bit_width or 32}"
        elif k is TypeKind.FLOAT:
            base = f"float{self.bit_width or 64}"
        elif k is TypeKind.DECIMAL:
            base = f"decimal({self.precision},{self.scale or 0})"
        elif k in (TypeKind.STRING, TypeKind.BINARY):
            prefix = "char" if (k is TypeKind.STRING and self.fixed) else k.value
            base = f"{prefix}({self.length})" if self.length is not None else prefix
        elif k is TypeKind.TIMESTAMP:
            tz = "tz" if self.with_timezone else "ntz"
            base = f"timestamp_{tz}" + (f"({self.precision})" if self.precision is not None else "")
        elif k is TypeKind.TIME:
            base = "time" + (f"({self.precision})" if self.precision is not None else "")
        elif k is TypeKind.ARRAY and self.element is not None:
            base = f"array<{self.element.signature()}>"
        elif k is TypeKind.MAP and self.key is not None and self.value is not None:
            base = f"map<{self.key.signature()},{self.value.signature()}>"
        elif k is TypeKind.STRUCT:
            inner = ",".join(f"{f.name}:{f.type.signature()}" for f in self.fields)
            base = f"struct<{inner}>"
        elif k is TypeKind.UNKNOWN:
            base = f"unknown({self.raw_source_type})"
        else:
            base = k.value
        return base if self.nullable else f"{base} not null"

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.signature()
