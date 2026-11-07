from typing import Any, TypedDict

class RequirementState(TypedDict, total=False):
    project_id: str
    workflow_id: str
    document_ids: list[str]
    original_requirement: str
    extracted_requirements: list[dict[str, Any]]
    clarification_questions: list[str]
    research_findings: list[dict[str, Any]]
    user_stories: list[dict[str, Any]]
    acceptance_criteria: list[dict[str, Any]]
    solution_design: dict[str, Any]
    implementation_tasks: list[dict[str, Any]]
    estimates: list[dict[str, Any]]
    validation_errors: list[dict[str, Any]]
    approval_status: str
    approved_by: str
    jira_issue_ids: list[str]
    github_issue_ids: list[str]
    generated_documents: list[dict[str, Any]]
    execution_log: list[dict[str, Any]]
