"""Connector exceptions."""


class ConnectorError(Exception):
    """Base exception for connector errors."""

    def __init__(self, message: str, connector_type: str = "unknown"):
        self.connector_type = connector_type
        super().__init__(message)


class ConnectionFailedError(ConnectorError):
    """Connection to source/target system failed."""


class InvalidIdentifierError(ConnectorError):
    """Schema/table/column identifier failed validation."""


class DiscoveryError(ConnectorError):
    """Schema/table/column discovery failed."""


class UnsupportedOperationError(ConnectorError):
    """Operation not supported by this connector."""
