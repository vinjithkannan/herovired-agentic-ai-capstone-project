"""State includes source-backed inputs and explicit, independently stored approvals."""
from typing import Any, TypedDict

class RequirementState(TypedDict, total=False):
    project_id: str
    backlog_id: str
    project_title: str
    source_requirement_ids: list[str]
    requirements: list[dict[str, Any]]
    evidence: dict[str, str]
    stories: list[dict[str, Any]]
    story_clearances: dict[str, dict[str, Any]]
    acceptance_criteria: list[dict[str, Any]]
    dependencies: list[dict[str, Any]]
    research_findings: list[dict[str, Any]]
    eligible_stories: list[dict[str, Any]]
    solution_design: dict[str, Any]
    implementation_tasks: list[dict[str, Any]]
    design_approval: str
    plan_approval: str
    workflow_status: str
    execution_log: list[dict[str, Any]]
