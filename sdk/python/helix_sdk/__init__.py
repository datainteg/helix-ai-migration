"""Helix Migration Python SDK.

Thin wrapper around the Helix REST API. Suitable for embedding inside
Airflow DAGs, Dagster assets, ad-hoc scripts.

Usage:
    from helix_sdk import Helix

    helix = Helix("https://helix.example.com", token="...")
    projects = helix.projects.list()          # list[dict] — back-compat
    page = helix.projects.paginated()         # PaginatedResponse with total/limit/offset
    run = helix.workflows.start(project_id=projects[0]["id"], requirement_id="...")
    print(helix.workflows.status(run["workflow_id"]))
"""

from helix_sdk.client import Helix, HelixError, PaginatedResponse

__version__ = "0.2.0"
__all__ = ["Helix", "HelixError", "PaginatedResponse"]
