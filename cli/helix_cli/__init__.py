"""Helix CLI — `helix` command wrapping the REST API.

Install (editable):
    cd cli && pip install -e .

Usage:
    helix login --api https://helix.example.com --email you@org.com
    helix projects list
    helix projects new --name "Oracle GL → Snowflake"
    helix workflow start --project <id> --requirement-id <req>
    helix workflow status <workflow-id>
    helix cost summary --days 30
    helix templates list
    helix cutover list --project <id>
"""

__version__ = "0.1.0"
