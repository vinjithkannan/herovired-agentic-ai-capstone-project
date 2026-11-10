from typing import Any, TypedDict

class StoryGenerationState(TypedDict, total=False):
    project_id: str
    analysis_id: str
    model: str
    requirements: list[dict[str, Any]]
    open_questions: list[dict[str, Any]]
    epics: list[dict[str, Any]]
    stories: list[dict[str, Any]]
    acceptance_criteria: list[dict[str, Any]]
    dependencies: list[dict[str, Any]]
    validation: dict[str, Any]
    errors: list[str]
