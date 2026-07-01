"""Connector Service Provider Interface (SPI) — the plugin contract.

The legacy connector was one fat, read-only ABC that forced every system into a
DB-table shape. The v2 contract is **capability-segregated**: a connector
implements only the capabilities it actually supports (metadata, data read/
write, job parsing, dependency extraction, code generation, validation,
deployment+rollback, testing). Each capability is a ``runtime_checkable``
Protocol, so the engine can discover what a connector can do.

The SPI lives in the engine (not in any vendor package) so the core owns the
contract and stays free of vendor imports; concrete connectors implement these
Protocols and declare a ``ConnectorManifest`` with versioned compatibility.
"""

from __future__ import annotations

from migration_engine.spi.contracts import (
    CAPABILITY_PROTOCOLS,
    CONTRACT_VERSION,
    Capability,
    CodeGenerator,
    ConnectionContext,
    ConnectorManifest,
    ConnectorRole,
    ConnectorTestResult,
    DataReader,
    DataWriter,
    DependencyProvider,
    DeployResult,
    Deployer,
    GeneratedArtifact,
    JobParser,
    MetadataProvider,
    Tester,
    Validator,
    detect_capabilities,
)
from migration_engine.spi.registry import ConnectorRegistry, RegistryEntry

__all__ = [
    "CAPABILITY_PROTOCOLS",
    "CONTRACT_VERSION",
    "Capability",
    "CodeGenerator",
    "ConnectionContext",
    "ConnectorManifest",
    "ConnectorRole",
    "ConnectorTestResult",
    "DataReader",
    "DataWriter",
    "DependencyProvider",
    "DeployResult",
    "Deployer",
    "GeneratedArtifact",
    "JobParser",
    "MetadataProvider",
    "Tester",
    "Validator",
    "detect_capabilities",
    "ConnectorRegistry",
    "RegistryEntry",
]
