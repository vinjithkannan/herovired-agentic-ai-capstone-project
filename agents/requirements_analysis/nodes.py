from langgraph.graph import END, START, StateGraph

from agents.requirements_analysis.ollama_client import chat_json
from agents.requirements_analysis.prompts import (
    extraction_prompt, classification_prompt, quality_prompt, validation_prompt,
)
from agents.requirements_analysis.state import AnalysisState
from app.services.database import get_connection
from app.services.embedding_service import embed_texts


def retrieve_context(state: AnalysisState) -> dict:
    query = state.get("question") or "Extract all functional and non-functional requirements, business rules and open questions."
    vector = embed_texts([query])[0]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT d.id, d.filename, c.chunk_index, c.content,
                              1 - (c.embedding <=> %s::vector) AS similarity
                       FROM document_chunks c JOIN documents d ON d.id=c.document_id
                       WHERE c.project_id=%s ORDER BY c.embedding <=> %s::vector LIMIT %s""",
                    (__import__('json').dumps(vector), state['project_id'], __import__('json').dumps(vector), state.get('top_k', 12)))
        rows = cur.fetchall()
    context = [{"document_id": str(r[0]), "filename": r[1], "chunk_index": r[2],
                "content": r[3], "similarity": round(float(r[4]), 4)} for r in rows]
    if not context:
        raise ValueError("No indexed passages found for this project. Upload a BRD before analysis.")
    return {"context": context, "model": state.get("model", "")}


def extract_requirements(state: AnalysisState) -> dict:
    data = chat_json(extraction_prompt(state))
    return {"extracted_requirements": data.get("requirements", [])}


def classify_requirements(state: AnalysisState) -> dict:
    data = chat_json(classification_prompt(state))
    return {"classified_requirements": data.get("requirements", [])}


def analyze_quality(state: AnalysisState) -> dict:
    data = chat_json(quality_prompt(state))
    return {"quality_findings": data.get("findings", []), "open_questions": data.get("open_questions", [])}


def validate_evidence(state: AnalysisState) -> dict:
    data = chat_json(validation_prompt(state))
    return {"validation": data}


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
