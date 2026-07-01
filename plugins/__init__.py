"""Connector plugins implementing the migration-engine SPI.

Plugins are vendor-specific and depend on ``migration_engine`` (never the other
way round). They are deliberately kept OUT of the pure core so the engine stays
free of vendor names. Each plugin implements one or more capability Protocols
from ``migration_engine.spi`` and declares a ``ConnectorManifest``.

Phase-1 plugins:
- ``db2``       — IBM DB2 source (metadata extraction into IR).
- ``snowflake`` — Snowflake target (DDL code generation from IR).
"""
