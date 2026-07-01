"""Capability contracts (Protocols) + supporting value types.

A connector mixes in whichever capability Protocols it supports. Because the
Protocols are ``runtime_checkable``, ``detect_capabilities`` can introspect a
connector instance and confirm it really provides what its manifest declares.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Optional, Protocol, Sequence, runtime_checkable

from migration_engine.ir.model import Dataset, Job, LineageEdge, MigrationIR
from migration_engine.ir.version import IR_SCHEMA_VERSION

# Bump for breaking changes to the capability Protocols below.
CONTRACT_VERSION = "0.1.0"


class Capability(str, Enum):
    METADATA = "metadata"          # extract datasets/schemas into IR
    DATA_READ = "data_read"        # read row batches from a source
    DATA_WRITE = "data_write"      # write row batches to a target
    JOB_PARSE = "job_parse"        # parse vendor jobs (.dsx/.sas) into IR jobs
    DEPENDENCY = "dependency"      # extract lineage/dependency edges
    CODEGEN = "codegen"            # generate target artifacts from IR
    VALIDATE = "validate"          # validate generated/applied output
    DEPLOY = "deploy"              # apply artifacts + rollback
    TEST = "test"                  # run capability/conformance tests


class ConnectorRole(str, Enum):
    SOURCE = "source"
    TARGET = "target"
    BOTH = "both"


@dataclass
class ConnectionContext:
    """Runtime connection info handed to a connector.

    ``config`` holds already-decrypted connection details (host, db, creds) —
    the host app decrypts via its DEK before calling, and connectors must never
    persist these back into the IR.
    """

    config: dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)


@dataclass(frozen=True)
class ConnectorTestResult:
    success: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeneratedArtifact:
    """A unit of generated target output (DDL, SQL, notebook, DAG, ...)."""

    path: str
    language: str            # "sql" | "python" | "yaml" | ...
    body: str
    kind: str = "code"       # "ddl" | "load" | "orchestration" | "code" | ...
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeployResult:
    """Outcome of a deployment, carrying a token usable to roll back."""

    success: bool
    journal_token: Optional[str] = None
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorManifest:
    """Self-description of a connector plugin (versioned for compatibility)."""

    name: str
    version: str
    role: ConnectorRole
    capabilities: frozenset[Capability]
    ir_version: str = IR_SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION
    vendor: str = ""
    description: str = ""


# ----- capability Protocols -------------------------------------------------
@runtime_checkable
class MetadataProvider(Protocol):
    def test_connection(self, ctx: ConnectionContext) -> ConnectorTestResult: ...
    def extract_datasets(self, ctx: ConnectionContext) -> list[Dataset]: ...


@runtime_checkable
class DependencyProvider(Protocol):
    def extract_lineage(self, ctx: ConnectionContext) -> list[LineageEdge]: ...


@runtime_checkable
class JobParser(Protocol):
    def parse_jobs(self, ctx: ConnectionContext, source: Any) -> list[Job]: ...


@runtime_checkable
class DataReader(Protocol):
    def read_batches(
        self, ctx: ConnectionContext, dataset: Dataset, *, batch_size: int = 10_000
    ) -> Iterable[Sequence[Any]]: ...


@runtime_checkable
class DataWriter(Protocol):
    def write_batches(
        self, ctx: ConnectionContext, dataset: Dataset, batches: Iterable[Sequence[Any]]
    ) -> int: ...


@runtime_checkable
class CodeGenerator(Protocol):
    def generate(self, ir: MigrationIR) -> list[GeneratedArtifact]: ...


@runtime_checkable
class Validator(Protocol):
    def validate(self, ctx: ConnectionContext, ir: MigrationIR) -> list[str]: ...


@runtime_checkable
class Deployer(Protocol):
    def deploy(self, ctx: ConnectionContext, artifacts: list[GeneratedArtifact]) -> DeployResult: ...
    def rollback(self, ctx: ConnectionContext, journal_token: str) -> DeployResult: ...


@runtime_checkable
class Tester(Protocol):
    def run_tests(self, ctx: ConnectionContext, ir: MigrationIR) -> bool: ...


# Capability <-> Protocol mapping for introspection.
CAPABILITY_PROTOCOLS: dict[Capability, type] = {
    Capability.METADATA: MetadataProvider,
    Capability.DEPENDENCY: DependencyProvider,
    Capability.JOB_PARSE: JobParser,
    Capability.DATA_READ: DataReader,
    Capability.DATA_WRITE: DataWriter,
    Capability.CODEGEN: CodeGenerator,
    Capability.VALIDATE: Validator,
    Capability.DEPLOY: Deployer,
    Capability.TEST: Tester,
}


def detect_capabilities(connector: Any) -> set[Capability]:
    """Introspect a connector instance for the capabilities it implements."""
    return {cap for cap, proto in CAPABILITY_PROTOCOLS.items() if isinstance(connector, proto)}
