"""Snowflake target connector plugin."""

from __future__ import annotations

from plugins.snowflake.rules import SNOWFLAKE_TYPE_RULES, build_mapper
from plugins.snowflake.target import MANIFEST, SnowflakeDDLGenerator, SnowflakeTarget

__all__ = [
    "SNOWFLAKE_TYPE_RULES",
    "build_mapper",
    "MANIFEST",
    "SnowflakeDDLGenerator",
    "SnowflakeTarget",
]
