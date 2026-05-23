"""
Code Analyzer and Code Review Agent output schemas.

Task 14: Typed Developer Execution agent outputs for safe review.
"""

from typing import Literal, Optional
from pydantic import BaseModel


class DependencyInfo(BaseModel):
    name: str
    type: str  # import, table, file, api
    risk: Optional[str] = None


class TransformationInfo(BaseModel):
    name: str
    description: str
    source: Optional[str] = None
    target: Optional[str] = None


class SecurityFinding(BaseModel):
    severity: Literal["info", "warning", "high", "critical"]
    description: str
    location: Optional[str] = None


class CodeAnalyzerOutput(BaseModel):
    """Output schema for Code Analyzer Agent."""
    summary: str
    inputs: list[str] = []
    outputs: list[str] = []
    dependencies: list[DependencyInfo] = []
    transformations: list[TransformationInfo] = []
    joins: list[str] = []
    filters: list[str] = []
    aggregations: list[str] = []
    risks: list[str] = []
    complexity_score: Optional[float] = None
    assumptions: list[str] = []
    limitations: list[str] = []
    confidence_score: Optional[float] = None


class CodeReviewOutput(BaseModel):
    """Output schema for Code Review Agent."""
    summary: str
    quality_findings: list[str] = []
    anti_patterns: list[str] = []
    formatting_issues: list[str] = []
    security_findings: list[SecurityFinding] = []
    performance_issues: list[str] = []
    maintainability_risks: list[str] = []
    hardcoded_secrets_detected: bool = False
    assumptions: list[str] = []
    limitations: list[str] = []
    confidence_score: Optional[float] = None


class ConversionOutput(BaseModel):
    """Output schema for Code Migration Agent."""
    source_type: str
    target_type: str
    generated_code: str
    assumptions: list[str] = []
    limitations: list[str] = []
    required_review: bool = True
    confidence_score: Optional[float] = None


class NotebookOutput(BaseModel):
    """Output schema for Notebook Generator Agent."""
    notebook_json: str  # JSON-serialized notebook structure
    cell_count: int
    markdown_cells: int
    code_cells: int
    validation_cells: int
    assumptions: list[str] = []
    limitations: list[str] = []
    confidence_score: Optional[float] = None
