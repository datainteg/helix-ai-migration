"""Versioned connector registry (v2).

Connectors register with a ``ConnectorManifest``. Registration:
- rejects connectors whose declared ``ir_version`` / ``contract_version`` is
  incompatible with the engine (backward-compat guarantee), and
- verifies the connector actually implements the capabilities it declares
  (no lying manifests).

The registry can then resolve connectors by name or by capability — this is the
seam the Migration Engine and the future Marketplace build on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from migration_engine.ir.version import IncompatibleIRVersionError, is_compatible
from migration_engine.spi.contracts import (
    CONTRACT_VERSION,
    Capability,
    ConnectorManifest,
    detect_capabilities,
)


class ContractVersionError(ValueError):
    """Raised when a connector's contract version is incompatible."""


class CapabilityMismatchError(ValueError):
    """Raised when a manifest declares capabilities the connector lacks."""


@dataclass(frozen=True)
class RegistryEntry:
    connector: Any
    manifest: ConnectorManifest


class ConnectorRegistry:
    """In-memory registry of connector plugins keyed by manifest name."""

    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}

    def register(self, connector: Any, manifest: ConnectorManifest) -> None:
        if not is_compatible(manifest.ir_version):
            raise IncompatibleIRVersionError(manifest.ir_version)
        if not is_compatible(manifest.contract_version, CONTRACT_VERSION):
            raise ContractVersionError(
                f"Connector {manifest.name!r} contract version {manifest.contract_version!r} "
                f"is incompatible with engine contract {CONTRACT_VERSION!r}."
            )
        actual = detect_capabilities(connector)
        undeclared = set(manifest.capabilities) - actual
        if undeclared:
            missing = ", ".join(sorted(c.value for c in undeclared))
            raise CapabilityMismatchError(
                f"Connector {manifest.name!r} declares capabilities it does not implement: {missing}."
            )
        self._entries[manifest.name] = RegistryEntry(connector=connector, manifest=manifest)

    def get(self, name: str) -> Any:
        return self._entries[name].connector

    def manifest(self, name: str) -> ConnectorManifest:
        return self._entries[name].manifest

    def names(self) -> list[str]:
        return sorted(self._entries)

    def with_capability(self, capability: Capability) -> list[str]:
        """Names of registered connectors that provide ``capability``."""
        return sorted(
            name for name, e in self._entries.items() if capability in e.manifest.capabilities
        )

    def __contains__(self, name: str) -> bool:
        return name in self._entries

    def __len__(self) -> int:
        return len(self._entries)
