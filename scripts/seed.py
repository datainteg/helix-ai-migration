#!/usr/bin/env python3
"""Seed example Sprint Management data for Helix Migration projects.

Usage:
    # Single project (default):
    python scripts/seed.py --org <ORG_UUID> --project <PROJECT_UUID>

    # Bulk — every project in an org:
    python scripts/seed.py --org <ORG_UUID> --all-projects-in-org

    # From the host machine pointing at the dev compose stack:
    DATABASE_URL=postgresql://helix:helix@localhost:5432/helix \\
        python scripts/seed.py --org <ORG_UUID> --project <PROJECT_UUID>

The seed is idempotent — running it twice produces the same DB state.
Wipes any pre-existing sprint rows for the target project(s) before
insert so the demo dataset is deterministic.

For dockerized dev you can also POST to
    /api/v1/projects/{project_id}/sprints/seed
which calls the same function with auth + audit.
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Helix Migration sprint data")
    parser.add_argument("--org", required=True, help="Organization UUID")
    parser.add_argument("--project", help="Project UUID (single-project mode)")
    parser.add_argument(
        "--all-projects-in-org",
        action="store_true",
        help="Seed every project belonging to --org (ignores --project)",
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres DSN (defaults to $DATABASE_URL)",
    )
    args = parser.parse_args()

    if not args.db_url:
        print("ERROR: DATABASE_URL not set and --db-url not provided", file=sys.stderr)
        return 2
    if not args.all_projects_in_org and not args.project:
        print("ERROR: pass --project <UUID> or --all-projects-in-org", file=sys.stderr)
        return 2

    os.environ["DATABASE_URL"] = args.db_url

    from app.db.session import SessionLocal
    from app.services.sprint_seed import seed_sprints_for_project
    from app.models.project import Project

    db = SessionLocal()
    try:
        if args.all_projects_in_org:
            projects = (
                db.query(Project)
                .filter(Project.organization_id == args.org)
                .all()
            )
            if not projects:
                print(f"ERROR: no projects for org {args.org}", file=sys.stderr)
                return 3
            print(f"Seeding {len(projects)} projects for org {args.org}…")
            totals = {"sprints_created": 0, "tasks_created": 0, "risks_created": 0,
                      "approvals_created": 0, "releases_created": 0,
                      "mapping_nodes_created": 0, "mapping_edges_created": 0,
                      "executions_created": 0, "duration_ms": 0}
            for p in projects:
                r = seed_sprints_for_project(db, args.org, p.id)
                for k in totals:
                    totals[k] += r.get(k, 0)
                print(f"  ✓ {p.id}  ({p.name or 'unnamed'})  {r['sprints_created']} sprints")
            print("\nTotals across org:")
            for k, v in totals.items():
                print(f"  {k:<24} {v}")
            return 0

        # Single-project path
        project = (
            db.query(Project)
            .filter(Project.id == args.project, Project.organization_id == args.org)
            .first()
        )
        if not project:
            print(f"ERROR: project {args.project} not found for org {args.org}", file=sys.stderr)
            return 3
        result = seed_sprints_for_project(db, args.org, args.project)
    finally:
        db.close()

    print("Seeded sprint dataset:")
    for k, v in result.items():
        print(f"  {k:<24} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
