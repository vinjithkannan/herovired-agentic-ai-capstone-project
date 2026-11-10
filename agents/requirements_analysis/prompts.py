import json


def _context(state: dict) -> str:
    return json.dumps(state.get("context", []), ensure_ascii=False, indent=2)


def extraction_prompt(state: dict) -> str:
    return f"""You are the Requirement Extraction Agent in ReqFlow AI.
Extract only requirements explicitly stated in the source passages. Do not invent requirements or convert open questions into requirements.
Return one valid JSON object: {{"requirements": [...]}}.
Each item MUST contain:
- temporary_id: sequential ID such as FR-001, NFR-001, BR-001 or CON-001
- statement: a complete, non-empty, testable sentence describing the requirement
- requirement_type: functional | non_functional | business_rule | constraint
- actor, capability, rationale
- source_refs: at least one object with filename, chunk_index and an EXACT verbatim quote copied from that passage
Use the exact source filename and numeric chunk_index shown in the input. Do not paraphrase the quote. Do not return blank strings. If a field is unknown, use an empty string except statement, requirement_type and source_refs, which are mandatory.

SOURCE PASSAGES:
{_context(state)}"""


def classification_prompt(state: dict) -> str:
    return f"""You are the Requirement Classification Agent.
For every input requirement, return the same temporary_id and enrich it with:
priority (must|should|could|undetermined), category (access_control|reporting|attendance|auditability|availability|performance|integration|other), ambiguity (low|medium|high), testability (testable|needs_clarification).
Preserve statement, requirement_type and source_refs exactly. Never omit or rewrite them. Do not invent business priority; use undetermined if the BRD does not establish it.
Return JSON: {{"requirements":[...]}}.

EXTRACTED REQUIREMENTS:
{json.dumps(state.get('extracted_requirements', []), ensure_ascii=False, indent=2)}"""


def quality_prompt(state: dict) -> str:
    return f"""You are the Requirements Quality Agent.
Identify only evidence-based issues that prevent an explicitly stated requirement from being implemented or tested:
issue_type (ambiguity|missing_detail|duplicate|conflict|untestable|scope_boundary), severity (low|medium|high), description, question_to_resolve, related_requirement_ids.
Severity guidance: high for unresolved eligibility/business policy, security/privacy, or performance/scalability targets that materially affect design; medium for workflow rules and validation details; low for non-blocking optional details. Do not label every issue low. A feature not mentioned is not automatically in scope. Keep open questions distinct from requirements.
Return JSON: {{"findings":[...], "open_questions":[...]}}.

SOURCE PASSAGES:
{_context(state)}

REQUIREMENTS:
{json.dumps(state.get('classified_requirements', []), ensure_ascii=False, indent=2)}"""
