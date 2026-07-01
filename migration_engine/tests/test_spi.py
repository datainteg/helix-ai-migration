"""Tests for the connector SPI: capability detection + versioned registry."""

from __future__ import annotations

import pytest

from migration_engine.ir.model import Dataset, MigrationIR
from migration_engine.ir.version import IncompatibleIRVersionError
from migration_engine.spi.contracts import (
    Capability,
    ConnectionContext,
    ConnectorManifest,
    ConnectorRole,
    ConnectorTestResult,
    DeployResult,
    GeneratedArtifact,
    detect_capabilities,
)
from migration_engine.spi.registry import (
    CapabilityMismatchError,
    ConnectorRegistry,
    ContractVersionError,
)


class FakeDB2Source:
    """Implements METADATA + DEPENDENCY."""

    def test_connection(self, ctx: ConnectionContext) -> ConnectorTestResult:
        return ConnectorTestResult(success=True, message="ok")

    def extract_datasets(self, ctx: ConnectionContext) -> list[Dataset]:
        return [Dataset(id="acct", name="ACCT", database="BEDROCK", schema="CORE")]

    def extract_lineage(self, ctx: ConnectionContext):
        return []


class FakeSnowflakeTarget:
    """Implements CODEGEN + DEPLOY."""

    def generate(self, ir: MigrationIR) -> list[GeneratedArtifact]:
        return [GeneratedArtifact(path="ddl.sql", language="sql", body="CREATE TABLE ...", kind="ddl")]

    def deploy(self, ctx: ConnectionContext, artifacts: list[GeneratedArtifact]) -> DeployResult:
        return DeployResult(success=True, journal_token="jrnl-1")

    def rollback(self, ctx: ConnectionContext, journal_token: str) -> DeployResult:
        return DeployResult(success=True, message=f"rolled back {journal_token}")


def _src_manifest(**over) -> ConnectorManifest:
    base = dict(
        name="db2", version="1.0.0", role=ConnectorRole.SOURCE,
        capabilities=frozenset({Capability.METADATA, Capability.DEPENDENCY}),
    )
    base.update(over)
    return ConnectorManifest(**base)


def test_detect_capabilities_matches_implementation():
    assert detect_capabilities(FakeDB2Source()) == {Capability.METADATA, Capability.DEPENDENCY}
    assert detect_capabilities(FakeSnowflakeTarget()) == {Capability.CODEGEN, Capability.DEPLOY}


def test_register_and_resolve_by_capability():
    reg = ConnectorRegistry()
    reg.register(FakeDB2Source(), _src_manifest())
    reg.register(FakeSnowflakeTarget(), ConnectorManifest(
        name="snowflake", version="1.0.0", role=ConnectorRole.TARGET,
        capabilities=frozenset({Capability.CODEGEN, Capability.DEPLOY}),
    ))
    assert reg.names() == ["db2", "snowflake"]
    assert reg.with_capability(Capability.METADATA) == ["db2"]
    assert reg.with_capability(Capability.CODEGEN) == ["snowflake"]
    assert "db2" in reg and len(reg) == 2


def test_manifest_cannot_overclaim_capabilities():
    reg = ConnectorRegistry()
    # FakeDB2Source does not implement DATA_READ.
    bad = _src_manifest(capabilities=frozenset({Capability.METADATA, Capability.DATA_READ}))
    with pytest.raises(CapabilityMismatchError):
        reg.register(FakeDB2Source(), bad)


def test_incompatible_ir_version_rejected():
    reg = ConnectorRegistry()
    with pytest.raises(IncompatibleIRVersionError):
        reg.register(FakeDB2Source(), _src_manifest(ir_version="9.0.0"))


def test_incompatible_contract_version_rejected():
    reg = ConnectorRegistry()
    with pytest.raises(ContractVersionError):
        reg.register(FakeDB2Source(), _src_manifest(contract_version="9.0.0"))


def test_capability_protocol_isinstance_runtime_checkable():
    from migration_engine.spi.contracts import CodeGenerator, MetadataProvider

    assert isinstance(FakeDB2Source(), MetadataProvider)
    assert not isinstance(FakeDB2Source(), CodeGenerator)
    assert isinstance(FakeSnowflakeTarget(), CodeGenerator)
