import json
import re
from difflib import SequenceMatcher
from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.requirements_analysis.ollama_client import chat_json
from agents.requirements_analysis.prompts import (
    extraction_prompt, classification_prompt, quality_prompt,
)
from agents.requirements_analysis.state import AnalysisState
from app.services.database import get_connection
from app.services.embedding_service import embed_texts


def _normalise_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip().casefold()


def _tokens(value: str) -> set[str]:
    ignored = {"the", "and", "for", "with", "from", "that", "this", "can", "should", "must", "are", "is", "to", "of", "in", "on", "a", "an", "as", "by", "their", "its"}
    return {t for t in re.findall(r"[a-z0-9]+", (value or "").casefold()) if len(t) > 2 and t not in ignored}


def _source_candidates(context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for item in context:
        # Keep sentence boundaries while tolerating Markdown headings and bullets.
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", item.get("content", "")):
            quote = sentence.strip().lstrip("#*- ").strip()
            if len(quote) >= 20:
                candidates.append({**item, "quote": quote})
    return candidates


def _canonical_source_refs(requirement: dict[str, Any], context: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    refs = requirement.get("source_refs") or requirement.get("sources") or []
    if isinstance(refs, dict):
        refs = [refs]
    canonical: list[dict[str, Any]] = []
    exact = False
    best_score = 0.0
    statement_tokens = _tokens(requirement.get("statement", ""))

    for ref in refs if isinstance(refs, list) else []:
        if not isinstance(ref, dict):
            continue
        filename = ref.get("filename")
        chunk_index = ref.get("chunk_index")
        quote = str(ref.get("quote") or ref.get("evidence_quote") or "").strip()
        for passage in context:
            if filename and filename != passage.get("filename"):
                continue
            if chunk_index is not None and str(chunk_index) != str(passage.get("chunk_index")):
                continue
            passage_text = _normalise_text(passage.get("content", ""))
            if quote and _normalise_text(quote) in passage_text:
                quote_tokens = _tokens(quote)
                quote_coverage = (len(statement_tokens & quote_tokens) / len(statement_tokens)) if statement_tokens else 0.0
                if quote_coverage >= 0.60:
                    exact = True
                    canonical.append({"filename": passage["filename"], "chunk_index": passage["chunk_index"], "quote": quote})
                    break

    if exact:
        return canonical, "supported"

    # If the model's quote is malformed or paraphrased, independently locate the
    # closest source sentence. Only accept a strong lexical match as supported.
    for candidate in _source_candidates(context):
        candidate_tokens = _tokens(candidate["quote"])
        if not statement_tokens or not candidate_tokens:
            continue
        coverage = len(statement_tokens & candidate_tokens) / len(statement_tokens)
        similarity = SequenceMatcher(None, _normalise_text(requirement.get("statement", "")), _normalise_text(candidate["quote"])).ratio()
        score = max(coverage, similarity)
        if score > best_score:
            best_score = score
            best = candidate

    if best_score >= 0.58:
        canonical = [{"filename": best["filename"], "chunk_index": best["chunk_index"], "quote": best["quote"]}]
        return canonical, "supported" if best_score >= 0.72 else "partial"
    if best_score >= 0.38:
        return [], "partial"
    return [], "unsupported"


def _normalise_requirement(item: dict[str, Any], index: int) -> dict[str, Any]:
    # Accommodate common small-model schema drift without losing the extracted text.
    statement = (item.get("statement") or item.get("requirement_statement") or item.get("requirement_text") or item.get("requirement_description") or item.get("description") or item.get("requirement") or item.get("title") or item.get("name") or item.get("details") or item.get("text") or "").strip()
    req_type = item.get("requirement_type") or item.get("type") or item.get("category_type") or ""
    req_id = item.get("temporary_id") or item.get("requirement_id") or item.get("id") or f"REQ-{index:03d}"
    if not req_type:
        prefix = str(req_id).upper().split("-")[0]
        req_type = {"FR": "functional", "NFR": "non_functional", "BR": "business_rule", "CON": "constraint"}.get(prefix, "")
    return {
        **item,
        "temporary_id": str(req_id),
        "statement": statement,
        "requirement_type": str(req_type).strip().lower(),
        "source_refs": item.get("source_refs") or item.get("sources") or [],
    }



def _explicit_requirements_from_brd(context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministically capture explicitly numbered BRD requirements missed by a small LLM."""
    found: dict[str, dict[str, Any]] = {}
    pattern = re.compile(r"\b(?P<prefix>NFR|FR|BR|CON)-(?P<number>\d{3})\s*[—–-]\s*(?P<title>[^:\n*]+):\s*(?P<body>.+)$", re.IGNORECASE)
    type_map = {"FR": "functional", "NFR": "non_functional", "BR": "business_rule", "CON": "constraint"}
    for passage in context:
        for raw_line in passage.get("content", "").splitlines():
            line = raw_line.strip()
            match = pattern.search(line)
            if not match:
                continue
            req_id = f"{match.group('prefix').upper()}-{match.group('number')}"
            title = match.group("title").strip().strip("* ")
            statement = re.sub(r"^\*+\s*", "", match.group("body").strip()).rstrip("* ").strip()
            if not statement:
                continue
            found[req_id] = {
                "temporary_id": req_id,
                "title": title,
                "statement": statement,
                "requirement_type": type_map[match.group("prefix").upper()],
                "actor": "",
                "capability": "",
                "rationale": "Extracted from an explicitly numbered BRD requirement.",
                "source_refs": [{"filename": passage["filename"], "chunk_index": passage["chunk_index"], "quote": line}],
            }
    return list(found.values())

def retrieve_context(state: AnalysisState) -> dict:
    query = state.get("question") or "Extract all functional and non-functional requirements, business rules and open questions."
    vector = embed_texts([query])[0]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT d.id, d.filename, c.chunk_index, c.content,
                              1 - (c.embedding <=> %s::vector) AS similarity
                       FROM document_chunks c JOIN documents d ON d.id=c.document_id
                       WHERE c.project_id=%s ORDER BY c.embedding <=> %s::vector LIMIT %s""",
                    (json.dumps(vector), state['project_id'], json.dumps(vector), state.get('top_k', 12)))
        rows = cur.fetchall()
    context = [{"document_id": str(r[0]), "filename": r[1], "chunk_index": r[2],
                "content": r[3], "similarity": round(float(r[4]), 4)} for r in rows]
    if not context:
        raise ValueError("No indexed passages found for this project. Upload a BRD before analysis.")
    return {"context": context, "model": state.get("model", "")}


def extract_requirements(state: AnalysisState) -> dict:
    data = chat_json(extraction_prompt(state))
    raw = data.get("requirements", [])
    if not isinstance(raw, list):
        raw = []
    requirements = [_normalise_requirement(x, i) for i, x in enumerate(raw, 1) if isinstance(x, dict)]
    by_id = {r["temporary_id"]: r for r in requirements}
    # Small local models can omit explicitly numbered NFRs. Supplement from BRD lines
    # without inventing anything: every supplemental item has an exact source-line quote.
    for explicit in _explicit_requirements_from_brd(state.get("context", [])):
        existing = by_id.get(explicit["temporary_id"])
        if existing:
            if not existing.get("statement"):
                existing["statement"] = explicit["statement"]
            if not existing.get("requirement_type"):
                existing["requirement_type"] = explicit["requirement_type"]
            if not existing.get("source_refs"):
                existing["source_refs"] = explicit["source_refs"]
        else:
            by_id[explicit["temporary_id"]] = explicit
    requirements = [r for r in by_id.values() if r.get("statement")]
    return {"extracted_requirements": requirements}


def classify_requirements(state: AnalysisState) -> dict:
    extracted = state.get("extracted_requirements", [])
    data = chat_json(classification_prompt(state))
    classified = data.get("requirements", [])
    by_id = {}
    if isinstance(classified, list):
        for item in classified:
            if isinstance(item, dict):
                key = item.get("temporary_id") or item.get("requirement_id") or item.get("id")
                if key:
                    by_id[str(key)] = item

    merged = []
    for original in extracted:
        extra = by_id.get(original["temporary_id"], {})
        # Extraction fields are authoritative; classification may enrich, never erase them.
        combined = {**extra, **original}
        for key in ("category", "ambiguity", "testability"):
            if extra.get(key) not in (None, ""):
                combined[key] = extra[key]
        # A priority label is accepted only when the BRD explicitly declares one.
        source_text = "\n".join(p.get("content", "") for p in state.get("context", []))
        explicit_priority = re.search(r"\bpriority\s*[:=–-]\s*(must|should|could)\b", source_text, re.IGNORECASE)
        combined["priority"] = extra.get("priority") if explicit_priority else "undetermined"
        combined.setdefault("ambiguity", "medium")
        combined.setdefault("testability", "needs_clarification")
        combined.setdefault("category", "other")
        merged.append(combined)
    return {"classified_requirements": merged}


def analyze_quality(state: AnalysisState) -> dict:
    data = chat_json(quality_prompt(state))
    findings = data.get("findings", [])
    questions = data.get("open_questions", [])
    return {
        "quality_findings": findings if isinstance(findings, list) else [],
        "open_questions": questions if isinstance(questions, list) else [],
    }


def validate_evidence(state: AnalysisState) -> dict:
    # Evidence validation is deterministic: never ask the same LLM to grade its own claims.
    context = state.get("context", [])
    validated = []
    for requirement in state.get("classified_requirements", []):
        refs, status = _canonical_source_refs(requirement, context)
        requirement["source_refs"] = refs
        validated.append({
            "temporary_id": requirement["temporary_id"],
            "evidence_status": status,
            "validation_note": {
                "supported": "A supporting quotation was matched to the retrieved source text.",
                "partial": "Some source wording is related, but the requirement needs human review.",
                "unsupported": "No sufficiently strong supporting passage was found in the retrieved context.",
            }[status],
        })
    counts = {status: sum(1 for x in validated if x["evidence_status"] == status) for status in ("supported", "partial", "unsupported")}
    return {"validation": {"requirements": validated, "overall_summary": f"Evidence check: {counts['supported']} supported, {counts['partial']} partial, {counts['unsupported']} unsupported. Verify partial and unsupported items before story generation."}}


def build_requirements_graph():
    graph = StateGraph(AnalysisState)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("extract_requirements", extract_requirements)
    graph.add_node("classify_requirements", classify_requirements)
    graph.add_node("analyze_quality", analyze_quality)
    graph.add_node("validate_evidence", validate_evidence)
    graph.add_edge(START, "retrieve_context")
    graph.add_edge("retrieve_context", "extract_requirements")
    graph.add_edge("extract_requirements", "classify_requirements")
    graph.add_edge("classify_requirements", "analyze_quality")
    graph.add_edge("analyze_quality", "validate_evidence")
    graph.add_edge("validate_evidence", END)
    return graph.compile()


requirements_analysis_graph = build_requirements_graph()
