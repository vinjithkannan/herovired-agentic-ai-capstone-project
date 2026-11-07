from pathlib import Path
from uuid import UUID, uuid4
import json
import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from psycopg.types.json import Jsonb

from app.core.config import settings
from app.schemas.documents import ProjectCreate, SearchRequest
from app.services.database import get_connection
from app.services.document_parser import SUPPORTED_EXTENSIONS, chunk_text, extract_text
from app.services.embedding_service import embed_texts

router = APIRouter(tags=["Documents and RAG"])
logger = logging.getLogger(__name__)
UPLOAD_DIR = Path("/app/data/uploads")
MAX_FILE_BYTES = 15 * 1024 * 1024


@router.get("/projects")
def list_projects():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name, description, status, created_at FROM projects ORDER BY created_at DESC")
        rows = cur.fetchall()
    return [dict(zip(["id", "name", "description", "status", "created_at"], row)) for row in rows]


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreate):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO projects(name, description) VALUES (%s, %s) RETURNING id, name, description, status, created_at", (payload.name, payload.description))
        row = cur.fetchone()
    return dict(zip(["id", "name", "description", "status", "created_at"], row))


@router.get("/projects/{project_id}/documents")
def list_documents(project_id: UUID):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT d.id, d.project_id, d.filename, d.file_type, d.processing_status, d.created_at,
                       COALESCE(c.chunk_count, 0) FROM documents d
                       LEFT JOIN (SELECT document_id, COUNT(*) AS chunk_count FROM document_chunks GROUP BY document_id) c
                       ON c.document_id=d.id WHERE d.project_id=%s ORDER BY d.created_at DESC""", (project_id,))
        rows = cur.fetchall()
    return [dict(zip(["id", "project_id", "filename", "file_type", "processing_status", "created_at", "chunk_count"], row)) for row in rows]


@router.post("/projects/{project_id}/documents", status_code=201)
async def upload_document(project_id: UUID, file: UploadFile = File(...)):
    extension = Path(file.filename or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(415, "Supported formats: PDF, DOCX, Markdown and TXT.")
    if not settings.openai_api_key:
        raise HTTPException(503, "OPENAI_API_KEY is not configured. Add it to .env and restart the backend.")
    content = await file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "Maximum upload size is 15 MB.")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    document_id = uuid4()
    safe_name = Path(file.filename or f"document{extension}").name
    stored_path = UPLOAD_DIR / f"{document_id}{extension}"
    stored_path.write_bytes(content)
    try:
        text = extract_text(str(stored_path), extension)
        chunks = chunk_text(text)
        vectors = embed_texts(chunks)
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM projects WHERE id=%s", (project_id,))
            if cur.fetchone() is None:
                raise HTTPException(404, "Project not found.")
            cur.execute("""INSERT INTO documents(id, project_id, filename, file_type, storage_path, processing_status)
                           VALUES (%s,%s,%s,%s,%s,'completed')""",
                        (document_id, project_id, safe_name, extension.lstrip('.'), str(stored_path)))
            for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
                cur.execute("""INSERT INTO document_chunks(document_id, project_id, chunk_index, content, embedding, metadata)
                               VALUES (%s,%s,%s,%s,%s::vector,%s)""",
                            (document_id, project_id, index, chunk, json.dumps(vector), Jsonb({"filename": safe_name, "source_type": extension.lstrip('.')})))
        return {"id": str(document_id), "project_id": str(project_id), "filename": safe_name,
                "processing_status": "completed", "character_count": len(text), "chunk_count": len(chunks)}
    except HTTPException:
        stored_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        logger.exception("Document ingestion failed")
        raise HTTPException(500, f"Document ingestion failed: {str(exc)}") from exc


@router.post("/rag/search")
def rag_search(payload: SearchRequest):
    try:
        query_vector = embed_texts([payload.question])[0]
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("""SELECT d.id, d.filename, c.chunk_index, c.content,
                                  1 - (c.embedding <=> %s::vector) AS similarity
                           FROM document_chunks c JOIN documents d ON d.id=c.document_id
                           WHERE c.project_id=%s ORDER BY c.embedding <=> %s::vector LIMIT %s""",
                        (json.dumps(query_vector), payload.project_id, json.dumps(query_vector), payload.top_k))
            rows = cur.fetchall()
        return {"question": payload.question, "results": [
            {"document_id": str(r[0]), "filename": r[1], "chunk_index": r[2], "content": r[3], "similarity": round(float(r[4]), 4)} for r in rows
        ]}
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logger.exception("RAG retrieval failed")
        raise HTTPException(500, f"RAG retrieval failed: {str(exc)}") from exc
