import json

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2)

def epic_prompt(state):
    return f"""You are the Epic Generation Agent for ReqFlow AI.
Group the validated requirements into a small set of coherent business epics.
Only use the requirement IDs supplied. Every epic must include source_requirement_ids.
Do not turn open questions into requirements. Do not invent scope.
Return JSON only: {{"epics":[{{"epic_key":"EPIC-001","title":"...","description":"...","business_value":"...","source_requirement_ids":["FR-001"]}}]}}
Create 2-6 epics when justified; fewer is acceptable. Do not create an empty epic.
VALIDATED REQUIREMENTS:
{_dump(state.get("requirements", []))}
OPEN QUESTIONS (context only; do not convert into scope):
{_dump(state.get("open_questions", []))}"""

def story_prompt(state):
    return f"""You are the Agile User Story Generation Agent.
Create implementation-ready user stories grouped under the supplied epics.
Use exactly this format for story_text: "As a [role], I want [capability], so that [benefit]."
Every story must cite one or more requirement IDs from the validated requirements and belong to one supplied epic_key.
Do not invent features from open questions. Do not assume answers to unresolved questions.
Return JSON only: {{"stories":[{{"story_key":"US-001","epic_key":"EPIC-001","title":"...","story_text":"As a ..., I want ..., so that ...","description":"...","source_requirement_ids":["FR-001"],"priority_recommendation":"must|should|could","priority_rationale":"...","assumptions":[]}}]}}
Generate a sensible, non-duplicative backlog. Prefer one independently valuable story per capability; split only when useful.
EPICS:
{_dump(state.get("epics", []))}
VALIDATED REQUIREMENTS:
{_dump(state.get("requirements", []))}
OPEN QUESTIONS (must remain unresolved):
{_dump(state.get("open_questions", []))}"""

def criteria_prompt(state):
    return f"""You are the Acceptance Criteria Agent.
For every supplied user story, generate 2-5 specific, testable acceptance criteria in Given-When-Then form.
Use criterion_text with "Given ..., When ..., Then ..." wording. Avoid vague words such as properly, quickly or user-friendly unless quantified by a source requirement.
Do not add policy decisions absent from the BRD. Where a story depends on an unresolved question, state that it requires product-owner clarification rather than guessing.
Return JSON only: {{"acceptance_criteria":[{{"story_key":"US-001","criterion_key":"AC-001","criterion_text":"Given ... When ... Then ...","test_type":"functional|security|performance|audit"}}]}}
STORIES:
{_dump(state.get("stories", []))}
REQUIREMENTS:
{_dump(state.get("requirements", []))}
OPEN QUESTIONS:
{_dump(state.get("open_questions", []))}"""

def estimation_prompt(state):
    return f"""You are the Agile Planning Agent.
For each supplied story, recommend Fibonacci story points from 1,2,3,5,8,13 and identify dependencies only when logically necessary.
Priority recommendation is advisory, not approved. Do not change story keys or source requirement IDs.
Return JSON only: {{"estimates":[{{"story_key":"US-001","story_points":3,"estimate_rationale":"...","priority_recommendation":"must|should|could","priority_rationale":"..."}}],"dependencies":[{{"story_key":"US-002","depends_on_story_key":"US-001","dependency_type":"blocks|relates_to","rationale":"..."}}]}}
STORIES:
{_dump(state.get("stories", []))}
EPICS:
{_dump(state.get("epics", []))}"""

def validation_prompt(state):
    return f"""You are the Backlog Quality Validation Agent.
Review each story and its acceptance criteria for clarity, INVEST qualities, testability, duplication, scope creep and requirement traceability.
Do not rewrite the backlog. Return issues only and a concise summary.
Return JSON only: {{"issues":[{{"story_key":"US-001","severity":"low|medium|high","issue_type":"clarity|testability|traceability|duplication|scope|dependency","description":"...","recommendation":"..."}}],"summary":"..."}}
STORIES:
{_dump(state.get("stories", []))}
ACCEPTANCE CRITERIA:
{_dump(state.get("acceptance_criteria", []))}
VALIDATED REQUIREMENTS:
{_dump(state.get("requirements", []))}"""
