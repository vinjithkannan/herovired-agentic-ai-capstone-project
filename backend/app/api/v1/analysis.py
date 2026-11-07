import json
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb

from agents.requirements_analysis.nodes import requirements_analysis_graph
from agents.requirements_analysis.ollama_client import OllamaError
from app.core.config import settings
from app.services.database import get_connection

router = APIRouter(prefix="/projects", tags=["Requirements Analysis"])
logger = logging.getLogger(__name__)


class AnalysisRequest(BaseModel):
    question: str | None = Field(default=None, max_length=2000)
    top_k: int = Field(default=12, ge=1, le=30)


@router.post("/{project_id}/analyze", status_code=201)
def analyze_project(project_id: UUID, payload: AnalysisRequest):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM projects WHERE id=%s", (project_id,))
        if cur.fetchone() is None:
            raise HTTPException(404, "Project not found.")
        cur.execute("SELECT COUNT(*) FROM document_chunks WHERE project_id=%s", (project_id,))
        if cur.fetchone()[0] == 0:
            raise HTTPException(400, "This project has no indexed document chunks. Upload a BRD first.")

    initial_state = {
        "project_id": str(project_id),
        "question": payload.question or "Extract all requirements and identify unresolved questions from the BRD.",
        "top_k": payload.top_k,
        "model": settings.ollama_model,
    }
    try:
        result = requirements_analysis_graph.invoke(initial_state)
    except OllamaError as exc:
        logger.exception("Ollama requirements analysis failed")
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logger.exception("Requirements analysis failed")
        raise HTTPException(500, f"Requirements analysis failed: {exc}") from exc

    response = {
        "project_id": str(project_id),
        "model": settings.ollama_model,
        "source_passages": result.get("context", []),
        "requirements": result.get("classified_requirements", []),
        "quality_findings": result.get("quality_findings", []),
        "open_questions": result.get("open_questions", []),
        "validation": result.get("validation", {}),
    }
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO analysis_runs(project_id, question, model_name, result)
                       VALUES (%s,%s,%s,%s) RETURNING id, created_at""",
                    (project_id, payload.question, settings.ollama_model, Jsonb(response)))
        run_id, created_at = cur.fetchone()
    response["analysis_id"] = str(run_id)
    response["created_at"] = created_at.isoformat()
    return response


@router.get("/{project_id}/analyses")
def list_analyses(project_id: UUID):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, status, question, model_name, created_at FROM analysis_runs WHERE project_id=%s ORDER BY created_at DESC LIMIT 20", (project_id,))
        rows = cur.fetchall()
    return [{"id": str(r[0]), "status": r[1], "question": r[2], "model": r[3], "created_at": r[4].isoformat()} for r in rows]
