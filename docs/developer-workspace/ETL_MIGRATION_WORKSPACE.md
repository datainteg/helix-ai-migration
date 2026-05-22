# ETL Migration Workspace

## Purpose

The ETL Migration Workspace helps teams inventory, analyze, review, and convert legacy migration and ETL logic into draft modern target artifacts.

Helix Migration generates draft migration code, notebook structures, validation plans, and reconciliation reports that must be reviewed and approved by humans before production use.

## ETL Migration Project Flow

```text
Create migration project
  -> Add subproject
  -> Upload ETL artifacts
  -> Analyze code and workflow dependencies
  -> Extract transformations
  -> Review quality and risks
  -> Generate draft target artifact
  -> Generate validation mapping
  -> Review side-by-side diff
  -> Approve or reject
  -> Link to validation and reconciliation plan
```

## DAG / Workflow Analysis

DAG / Workflow Review Agent should detect:

- Cycles
- Duplicate task IDs
- Missing retries
- Missing timeouts
- Risky sensors
- Scheduling issues
- Missing owners
- Dependency fan-out risks
- Long-running task risks

## Transformation Extraction

Code Analyzer Agent should extract:

- Source inputs
- Target outputs
- Joins
- Filters
- Aggregations
- Window logic
- Data type conversions
- Business rules
- Error handling
- External dependencies

## Notebook Generation

Notebook Generator Agent should create Databricks notebook-style draft structures:

- Markdown overview cells
- Setup/import cells
- Source read cells
- Transformation cells
- Target write cells
- Validation cells
- Execution notes
- Assumptions and limitations

## Migration Readiness Scoring

Migration readiness score can use:

- Code complexity
- Number of dependencies
- Hardcoded secrets
- Missing validations
- DAG quality
- Conversion confidence
- Human approval status
- Validation mapping completeness

## Supported Future Migration Patterns

- Python script to Databricks notebook draft
- SQL job to optimized SQL / dbt-style model draft
- SAS logic to Databricks notebook draft
- Legacy ETL script to PySpark draft
- Airflow DAG review and modernization
- DAG dependency and cycle validation
- Workflow scheduling, retry, timeout, and sensor review
- Multi-file ETL project analysis
- Generated validation plan from extracted logic

MVP must not execute uploaded ETL scripts or DAGs. It should analyze, review, generate draft structures, show diffs, and require human approval.

## Related Docs

| Doc | What it covers |
|---|---|
| `DEVELOPER_WORKSPACE.md` | Overall workspace layout, artifact types, versioning, approval lifecycle |
| `CODE_REVIEW_CENTER.md` | Upload, AI analysis, review comments, diff viewer, export |
| `../../AGENT_WORKFLOW.md` | DAG/Workflow Review, Code Migration, and Notebook Generator agent roles |
| `../../API_DESIGN.md` | DAG review, conversion, and notebook generation APIs |
| `../storage/ARTIFACT_STORAGE.md` | Artifact metadata and file storage |
| `../security/SAFE_EXECUTION.md` | Safe execution rules — analysis only in MVP |
