"""Migration templates — pre-baked starter packs.

Each template encodes the common gotchas for a source→target pair: default
validation rules, recon thresholds, and BMAD agent prompt overrides. Operators
clone one into a fresh project and the planning agents inherit the overrides.

Templates ship as code (Python dict) rather than DB rows so they version with
the repo and stay reproducible across deployments. Operators with custom
templates add new entries to TEMPLATES and the catalog endpoint surfaces them.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_organization_id
from app.auth.jwt import get_current_user_id
from app.api.audit import write_audit
from app.schemas.project import ProjectCreate
from app.services.project_service import create_project
from app.models.validation import ValidationRule

router = APIRouter(tags=["migration-templates"])


class TemplateSummary(BaseModel):
    """Catalog-view row — no agent_prompts (kept server-side until clone)."""

    id: str
    name: str
    source: str
    target: str
    summary: str
    risk_level: str
    validation_rules: list[dict] = []
    recon_threshold_pct: float | None = None


class TemplateDetail(TemplateSummary):
    """Detail view includes agent prompt overrides."""

    agent_prompts: dict[str, str] = {}


class CloneTemplateResponse(BaseModel):
    project_id: str
    # `project` mirrors the project_service.create_project return shape;
    # kept as a flexible dict because the underlying service can evolve
    # (ProjectResponse fields change with the data model).
    project: dict[str, Any]
    validation_rule_ids: list[str]
    agent_prompts: dict[str, str] = {}
    recon_threshold_pct: float | None = None


# Each template:
#   id            stable slug
#   source/target connector types (matches LLMProviderType + ConnectorType)
#   summary       one-liner shown in the catalog
#   risk_level    default risk for the cloned project
#   validation_rules  pre-attached rules (rule_type, definition)
#   recon_threshold_pct  pre-flip diff tolerance
#   agent_prompts default per-agent prompt suffix appended at planning time
TEMPLATES: list[dict] = [
    {
        "id": "oracle-to-snowflake",
        "name": "Oracle → Snowflake",
        "source": "oracle",
        "target": "snowflake",
        "summary": "Classic lift-and-shift. Handles VARCHAR2 → VARCHAR, NUMBER(p,s) → NUMBER, DATE → TIMESTAMP_NTZ, CLOB → VARCHAR(MAX). Recon at 0.01% tolerance.",
        "risk_level": "medium",
        "validation_rules": [
            {"rule_type": "schema_compare", "definition": "{}"},
            {"rule_type": "row_count",      "definition": ""},
        ],
        "recon_threshold_pct": 0.01,
        "agent_prompts": {
            "architect": "Map every NUMBER(p,s) explicitly. Reject implicit NUMBER without precision — Snowflake's behaviour differs from Oracle's.",
            "dev":       "Use Snowflake COPY INTO from S3 staging, not row-by-row INSERT.",
        },
    },
    {
        "id": "sas-to-databricks",
        "name": "SAS → Databricks",
        "source": "sas",
        "target": "databricks",
        "summary": "Convert SAS data steps + PROC SQL to PySpark on Databricks. Validates row count, sum-of-numeric-columns, distinct-count of keys.",
        "risk_level": "high",
        "validation_rules": [
            {"rule_type": "row_count",   "definition": ""},
            {"rule_type": "duplicate",   "definition": ""},
            {"rule_type": "distribution","definition": ""},
        ],
        "recon_threshold_pct": 0.1,
        "agent_prompts": {
            "analyst": "Identify FORMAT/INFORMAT statements early — they often encode business rules that must port to Databricks UDFs.",
            "dev":     "Prefer Databricks SQL over PySpark when the source SAS step is purely SELECT/JOIN.",
        },
    },
    {
        "id": "sqlserver-to-postgres",
        "name": "SQL Server → Postgres",
        "source": "sqlserver",
        "target": "postgres",
        "summary": "DATETIME2 → TIMESTAMP, NVARCHAR → VARCHAR, IDENTITY → GENERATED ALWAYS AS IDENTITY. Stored procedures flagged for manual review.",
        "risk_level": "medium",
        "validation_rules": [
            {"rule_type": "schema_compare", "definition": "{}"},
            {"rule_type": "row_count",      "definition": ""},
            {"rule_type": "null",           "definition": ""},
        ],
        "recon_threshold_pct": 0.0,
        "agent_prompts": {
            "architect": "T-SQL stored procedures must be flagged as 'manual conversion required' — do not auto-port them.",
        },
    },
    {
        "id": "saphana-to-bigquery",
        "name": "SAP HANA → BigQuery",
        "source": "custom",
        "target": "bigquery",
        "summary": "HANA calculation views → BigQuery materialized views. Partition by date, cluster by primary key.",
        "risk_level": "high",
        "validation_rules": [
            {"rule_type": "row_count",      "definition": ""},
            {"rule_type": "schema_compare", "definition": "{}"},
        ],
        "recon_threshold_pct": 0.05,
        "agent_prompts": {
            "architect": "Always emit partition + cluster keys on BigQuery DDL. Default partition = ingestion date if no temporal column.",
            "dev":       "Replace HANA WINDOW functions with BigQuery analytic functions; warn on RESERVOIR_SAMPLE — no direct equivalent.",
        },
    },
    {
        "id": "teradata-to-databricks",
        "name": "Teradata → Databricks",
        "source": "custom",
        "target": "databricks",
        "summary": "QUALIFY → ROW_NUMBER subqueries, PERIOD type → STRUCT, MULTILOAD/FASTLOAD → Auto Loader.",
        "risk_level": "high",
        "validation_rules": [
            {"rule_type": "row_count",   "definition": ""},
            {"rule_type": "duplicate",   "definition": ""},
        ],
        "recon_threshold_pct": 0.05,
        "agent_prompts": {
            "architect": "Drop UPI/NUPI distinctions; on Delta use Z-ORDER + identity column instead.",
            "dev":       "Convert SELECT TOP N to LIMIT N; QUALIFY clause requires explicit ROW_NUMBER() OVER subquery.",
        },
    },
]


_TEMPLATES_BY_ID = {t["id"]: t for t in TEMPLATES}


class CloneTemplateRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=64)
    project_name: str = Field(min_length=1, max_length=255)
    project_description: str | None = Field(default=None, max_length=2048)


@router.get("/migration-templates", response_model=list[TemplateSummary])
def list_templates(user_id: str = Depends(get_current_user_id)):
    """Public catalog of available starter packs. Auth required to keep
    template list off unauthenticated reconnaissance.

    `agent_prompts` is intentionally stripped — that field is returned on
    detail (`GET /migration-templates/{id}`) and on clone, but not in
    bulk catalog browsing.
    """
    return [
        TemplateSummary(**{k: v for k, v in t.items() if k != "agent_prompts"})
        for t in TEMPLATES
    ]


@router.get("/migration-templates/{template_id}", response_model=TemplateDetail)
def get_template(template_id: str, user_id: str = Depends(get_current_user_id)):
    tpl = _TEMPLATES_BY_ID.get(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Template {template_id!r} not found")
    return TemplateDetail(**tpl)


@router.post("/migration-templates/clone", status_code=201, response_model=CloneTemplateResponse)
def clone_template(
    data: CloneTemplateRequest,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Materialize a template into a real project + validation rules.

    Side effects: creates one Project row + N ValidationRule rows. Agent
    prompt overrides are returned in the response so the frontend can pass
    them to the next planning call (or persist them in the project's
    extra_config — not yet wired).
    """
    tpl = _TEMPLATES_BY_ID.get(data.template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Template {data.template_id!r} not found")

    project = create_project(
        db, org_id, user_id,
        ProjectCreate(
            name=data.project_name,
            description=data.project_description or tpl["summary"],
            risk_level=tpl.get("risk_level", "medium"),
            migration_type=f"{tpl['source']}-to-{tpl['target']}",
        ),
    )

    rules_created: list[str] = []
    for rule in tpl.get("validation_rules", []):
        row = ValidationRule(
            project_id=project.id,
            rule_type=rule["rule_type"],
            definition=rule.get("definition", ""),
        )
        db.add(row)
        db.flush()
        rules_created.append(row.id)
    db.commit()

    write_audit(db, org_id=org_id, actor_id=user_id, action="template_cloned",
                entity_type="project", entity_id=project.id,
                meta={"template_id": data.template_id, "rules": len(rules_created)},
                request=request)

    project_dict = (
        project.model_dump() if hasattr(project, "model_dump") else dict(project)  # type: ignore[arg-type]
    )
    return CloneTemplateResponse(
        project_id=project.id,
        project=project_dict,
        validation_rule_ids=rules_created,
        agent_prompts=tpl.get("agent_prompts", {}),
        recon_threshold_pct=tpl.get("recon_threshold_pct"),
    )
