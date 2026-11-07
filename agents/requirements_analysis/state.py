from typing import Any, TypedDict


class AnalysisState(TypedDict, total=False):
    project_id: str
    question: str
    top_k: int
    context: list[dict[str, Any]]
    extracted_requirements: list[dict[str, Any]]
    classified_requirements: list[dict[str, Any]]
    quality_findings: list[dict[str, Any]]
    open_questions: list[Any]
    validation: dict[str, Any]
    errors: list[str]
    model: str
