import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request
from app.services.auth_service import record_audit
from pydantic import BaseModel
from psycopg.types.json import Jsonb

from app.core.config import settings
from app.services.database import get_connection
from agents.story_generation.graph import story_generation_graph
from agents.story_generation.quality import validate as validate_quality
from app.services.story_clearance import clearance_report
from agents.story_generation.repair import repair_backlog
from agents.requirements_analysis.ollama_client import OllamaError

router = APIRouter(prefix="/projects", tags=["Agile Backlog"])
logger = logging.getLogger(__name__)

class BacklogGenerateRequest(BaseModel):
    analysis_id: UUID
    include_partial_evidence: bool = False

@router.post("/{project_id}/backlogs/generate", status_code=201)
def generate_backlog(project_id: UUID, payload: BacklogGenerateRequest):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM projects WHERE id=%s", (project_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Project not found.")
        cur.execute("""SELECT result FROM analysis_runs
                       WHERE id=%s AND project_id=%s""", (payload.analysis_id, project_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Analysis run not found for this project.")
        analysis = row[0]
    requirements = analysis.get("requirements", [])
    validation = analysis.get("validation", {}).get("requirements", [])
    evidence = {x.get("temporary_id"): x.get("evidence_status") for x in validation}
    accepted = []
    for req in requirements:
        status = evidence.get(req.get("temporary_id"), "unsupported")
        if status == "supported" or (payload.include_partial_evidence and status == "partially_supported"):
            if req.get("statement") and req.get("temporary_id"):
                accepted.append(req)
    if not accepted:
        raise HTTPException(400, "No evidence-supported requirements are available. Run Phase 3 analysis or review evidence first.")
    initial = {
        "project_id": str(project_id),
        "analysis_id": str(payload.analysis_id),
        "model": settings.ollama_model,
        "requirements": accepted,
        "open_questions": analysis.get("open_questions", []),
    }
    try:
        result = story_generation_graph.invoke(initial)
    except OllamaError as exc:
        logger.exception("Ollama backlog generation failed")
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logger.exception("Backlog generation failed")
        raise HTTPException(500, f"Backlog generation failed: {exc}") from exc

    response = {
        "project_id": str(project_id),
        "analysis_id": str(payload.analysis_id),
        "model": settings.ollama_model,
        "epics": result.get("epics", []),
        "stories": result.get("stories", []),
        "acceptance_criteria": result.get("acceptance_criteria", []),
        "dependencies": result.get("dependencies", []),
        "validation": result.get("validation", {}),
        "source_requirement_ids": [r["temporary_id"] for r in accepted],
        "open_questions": analysis.get("open_questions", []),
    }
    backlog_id, created_at = _persist_backlog(project_id, payload.analysis_id, response)
    for story in response["stories"]:
        story["approval_status"] = "pending"
    response["backlog_id"] = str(backlog_id)
    response["created_at"] = created_at.isoformat()
    return response

@router.get("/{project_id}/backlogs")
def list_backlogs(project_id: UUID):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id, analysis_run_id, model_name, status, created_at
                       FROM backlog_runs WHERE project_id=%s ORDER BY created_at DESC LIMIT 20""", (project_id,))
        rows = cur.fetchall()
    return [{"id": str(r[0]), "analysis_id": str(r[1]), "model": r[2], "status": r[3], "created_at": r[4].isoformat()} for r in rows]

@router.get("/{project_id}/backlogs/{backlog_id}")
def get_backlog(project_id: UUID, backlog_id: UUID):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT result, created_at FROM backlog_runs WHERE id=%s AND project_id=%s""", (backlog_id, project_id))
        row = cur.fetchone()
        if row:
            cur.execute("SELECT story_key, approval_status FROM user_stories WHERE backlog_run_id=%s", (backlog_id,))
            approvals = dict(cur.fetchall())
    if not row:
        raise HTTPException(404, "Backlog not found.")
    result = row[0]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT a.result FROM analysis_runs a JOIN backlog_runs b ON b.analysis_run_id=a.id WHERE b.id=%s", (backlog_id,))
        source_row = cur.fetchone()
    if source_row:
        req_ids = set(result.get("source_requirement_ids", []))
        requirements = [r for r in source_row[0].get("requirements", []) if r.get("temporary_id") in req_ids]
        evidence = {v.get('temporary_id'): v.get('evidence_status') for v in source_row[0].get('validation', {}).get('requirements', [])}
        result['story_clearances'], result['validation'] = clearance_report(result, requirements, evidence)
    for story in result.get("stories", []):
        story["approval_status"] = approvals.get(story.get("story_key"), "pending")
    result["backlog_id"] = str(backlog_id)
    result["created_at"] = row[1].isoformat()
    return result

class StoryApprovalRequest(BaseModel):
    status: str

@router.patch("/{project_id}/backlogs/{backlog_id}/stories/{story_key}/approval")
def update_story_approval(project_id: UUID, backlog_id: UUID, story_key: str, payload: StoryApprovalRequest, request: Request):
    if payload.status not in {"pending", "approved", "rejected", "needs_revision"}:
        raise HTTPException(422, "status must be pending, approved, rejected or needs_revision")
    if payload.status == "approved":
        # Revalidate persisted backlog and its original source before changing approval.
        current = get_backlog(project_id, backlog_id)
        if story_key not in {s["story_key"] for s in current.get("stories", [])}:
            raise HTTPException(404, "Story not found")
        clearance = current.get('story_clearances', {}).get(story_key)
        if not clearance or clearance['status'] != 'quality_cleared':
            raise HTTPException(409, "Story requires quality clearance before approval. Resolve blocking findings and assumptions.")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE user_stories SET approval_status=%s
                       WHERE backlog_run_id=%s AND story_key=%s
                         AND EXISTS (SELECT 1 FROM backlog_runs WHERE id=%s AND project_id=%s)
                       RETURNING story_key, approval_status""",
                    (payload.status, backlog_id, story_key, backlog_id, project_id))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Story not found in this project's backlog")
    record_audit(request.state.user['id'],'story.approval', 'story', story_key,
                 {'backlog_id':str(backlog_id),'status':row[1]})
    return {"story_key": row[0], "approval_status": row[1]}

def _persist_backlog(project_id, analysis_id, response):
    """Atomic immutable snapshot insert, same normalized tables as Phase 4."""
    settings_model = response["model"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO backlog_runs(project_id, analysis_run_id, model_name, result)
                       VALUES (%s,%s,%s,%s) RETURNING id, created_at""",
                    (project_id, analysis_id, settings_model, Jsonb(response)))
        backlog_id, created_at = cur.fetchone()
        epic_ids = {}
        for epic in response["epics"]:
            cur.execute("""INSERT INTO epics(backlog_run_id, epic_key, title, description, business_value, source_requirement_ids)
                           VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (backlog_id, epic["epic_key"], epic["title"], epic["description"], epic.get("business_value", ""), Jsonb(epic["source_requirement_ids"])))
            epic_ids[epic["epic_key"]] = cur.fetchone()[0]
        story_ids = {}
        for story in response["stories"]:
            epic_id = epic_ids.get(story["epic_key"])
            if not epic_id:
                continue
            cur.execute("""INSERT INTO user_stories(backlog_run_id, epic_id, story_key, title, story_text, description,
                           source_requirement_ids, priority_recommendation, priority_rationale, story_points,
                           estimate_rationale, assumptions)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (backlog_id, epic_id, story["story_key"], story["title"], story["story_text"], story.get("description", ""),
                         Jsonb(story["source_requirement_ids"]), story["priority_recommendation"], story["priority_rationale"],
                         story.get("story_points"), story.get("estimate_rationale", ""), Jsonb(story.get("assumptions", []))))
            story_ids[story["story_key"]] = cur.fetchone()[0]
        for criterion in response["acceptance_criteria"]:
            story_id = story_ids.get(criterion["story_key"])
            if story_id:
                cur.execute("""INSERT INTO acceptance_criteria(user_story_id, criterion_key, criterion_text, test_type)
                               VALUES (%s,%s,%s,%s)""",
                            (story_id, criterion["criterion_key"], criterion["criterion_text"], criterion["test_type"]))
        for dependency in response["dependencies"]:
            story_id = story_ids.get(dependency["story_key"])
            depends_id = story_ids.get(dependency["depends_on_story_key"])
            if story_id and depends_id:
                cur.execute("""INSERT INTO story_dependencies(backlog_run_id, story_id, depends_on_story_id, dependency_type, rationale)
                               VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                            (backlog_id, story_id, depends_id, dependency["dependency_type"], dependency.get("rationale", "")))
    return backlog_id, created_at


class BacklogRepairRequest(BaseModel):
    use_ollama: bool = True

@router.post("/{project_id}/backlogs/{backlog_id}/repair", status_code=201)
def repair_saved_backlog(project_id: UUID, backlog_id: UUID, payload: BacklogRepairRequest):
    """Generate new immutable version. Never UPDATE source run or its approvals."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT b.result, b.analysis_run_id, a.result
                       FROM backlog_runs b
                       JOIN analysis_runs a ON a.id=b.analysis_run_id
                       WHERE b.id=%s AND b.project_id=%s""", (backlog_id, project_id))
        row=cur.fetchone()
    if not row:
        raise HTTPException(404, "Backlog not found in this project")
    original, analysis_id, analysis = row
    supported = set(original.get('source_requirement_ids', []))
    validation = analysis.get('validation', {}).get('requirements', [])
    evidence={v.get('temporary_id'):v.get('evidence_status') for v in validation}
    requirements=[r for r in analysis.get('requirements', [])
                  if r.get('temporary_id') in supported and evidence.get(r.get('temporary_id')) in ('supported','partially_supported')]
    if not requirements:
        raise HTTPException(409,"Original supported requirements unavailable; repair aborted.")
    try:
        repaired, audit = repair_backlog(original, requirements, use_ollama=payload.use_ollama)
    except Exception as exc:
        logger.exception("Backlog repair failed")
        raise HTTPException(500,"Backlog repair failed; original remains unchanged.") from exc
    # Require measurable improvement, otherwise do not create a misleading repair version.
    if audit['after_blocking_findings'] >= audit['before_blocking_findings']:
        raise HTTPException(409,"Repair did not reduce blocking findings. Original unchanged; manual review required.")
    repaired['repair_of_backlog_id']=str(backlog_id)
    repaired['repair_version']=int(original.get('repair_version',0))+1
    repaired['repair_audit']=audit
    repaired['project_id']=str(project_id)
    repaired['analysis_id']=str(analysis_id)
    repaired['model']=settings.ollama_model if payload.use_ollama else original.get('model',settings.ollama_model)
    repaired['source_requirement_ids']=[r['temporary_id'] for r in requirements]
    # Reset all approvals for newly generated versions; original approvals remain unchanged.
    new_id, created_at=_persist_backlog(project_id,analysis_id,repaired)
    for story in repaired['stories']:
        story['approval_status']='pending'
    repaired['backlog_id']=str(new_id)
    repaired['created_at']=created_at.isoformat()
    return repaired
