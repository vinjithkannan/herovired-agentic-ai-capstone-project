import json


def _context(state: dict) -> str:
    return json.dumps(state.get("context", []), ensure_ascii=False, indent=2)


def extraction_prompt(state: dict) -> str:
    return f"""You are the Requirement Extraction Agent in ReqFlow AI.
Extract only requirements explicitly supported by the source passages below.
Return one valid JSON object with key `requirements`, an array of objects with:
`temporary_id` (FR-001/NFR-001/BR-001 style), `statement` (one testable requirement),
`requirement_type` (functional|non_functional|business_rule|constraint), `actor`,
`capability`, `rationale`, `source_refs` (array of objects containing `filename`, `chunk_index`, `quote`).
Every requirement MUST have at least one source_ref with a short verbatim quote from the supplied context.
Do not infer missing requirements. Do not convert an open question into a requirement.
If no supported requirements exist, return an empty array.

SOURCE PASSAGES:\n{_context(state)}"""


def classification_prompt(state: dict) -> str:
    return f"""You are the Requirement Classification Agent.
Review the extracted requirements and classify each by `priority` (must|should|could|undetermined),
`category` (access_control|reporting|attendance|auditability|availability|performance|integration|other),
`ambiguity` (low|medium|high), and `testability` (testable|needs_clarification).
Do not change the requirement statement or source_refs. Do not invent business priority.
Use `undetermined` if the source does not establish priority. Return JSON: {{"requirements":[...]}}.

EXTRACTED REQUIREMENTS:\n{json.dumps(state.get('extracted_requirements', []), ensure_ascii=False, indent=2)}"""


def quality_prompt(state: dict) -> str:
    return f"""You are the Requirements Quality Agent.
Inspect the source passages and classified requirements. Identify only evidence-based issues:
`issue_type` (ambiguity|missing_detail|duplicate|conflict|untestable|scope_boundary),
`severity` (low|medium|high), `description`, `question_to_resolve`, and `related_requirement_ids`.
Important: a feature not mentioned in the BRD is not automatically in scope. Flag it as missing only
when needed to make an explicitly stated requirement implementable. Keep open questions distinct.
Return JSON: {{"findings":[...], "open_questions":[...]}}.

SOURCE PASSAGES:\n{_context(state)}

REQUIREMENTS:\n{json.dumps(state.get('classified_requirements', []), ensure_ascii=False, indent=2)}"""


def validation_prompt(state: dict) -> str:
    return f"""You are the Evidence Validation Agent. Check every requirement against the source passages.
A requirement is `supported` only if at least one source quote substantively supports its statement.
Return JSON with `requirements` array containing each `temporary_id`, `evidence_status` (supported|unsupported|partial),
`validation_note`; and `overall_summary`. Do not rewrite requirements or create new ones.

SOURCE PASSAGES:\n{_context(state)}

REQUIREMENTS:\n{json.dumps(state.get('classified_requirements', []), ensure_ascii=False, indent=2)}"""
