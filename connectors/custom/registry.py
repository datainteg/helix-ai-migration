"""Custom connector registry — register and discover custom connectors."""

from __future__ import annotations

from typing import Type

from connectors.base.connector import BaseConnector

_registry: dict[str, Type[BaseConnector]] = {}


def register_connector(connector_type: str, connector_class: Type[BaseConnector]) -> None:
    """Register a custom connector class."""
    if not issubclass(connector_class, BaseConnector):
        raise TypeError(f"{connector_class.__name__} must extend BaseConnector")
    _registry[connector_type] = connector_class


def get_connector(connector_type: str) -> Type[BaseConnector] | None:
    """Get a registered custom connector class."""
    return _registry.get(connector_type)


def list_registered_connectors() -> dict[str, str]:
    """List all registered custom connectors with display names."""
    return {k: v.display_name for k, v in _registry.items()}


def validate_connector_class(connector_class: Type[BaseConnector]) -> bool:
    """Validate that a class implements the BaseConnector interface."""
    return issubclass(connector_class, BaseConnector) and hasattr(connector_class, "connector_type")
