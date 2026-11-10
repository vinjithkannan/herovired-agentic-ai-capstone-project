from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb
from app.services.auth_service import require_roles, record_audit
from app.services.evaluation import evaluate
from app.services.database import get_connection
from app.api.v1.backlog import get_backlog

router=APIRouter(prefix='/projects',tags=['Phase 6 Evaluation'])
class EvaluationRequest(BaseModel):
    expected_requirement_ids: list[str] = Field(min_length=1,max_length=500)

@router.post('/{project_id}/backlogs/{backlog_id}/evaluate',status_code=201)
def evaluate_backlog(project_id:UUID,backlog_id:UUID,payload:EvaluationRequest,
                     user=Depends(require_roles(
                                                     'admin',
                                                     'engineer',
                                                     'product_owner'
                                                 ))):
    backlog=get_backlog(project_id,backlog_id)
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("SELECT a.result FROM analysis_runs a JOIN backlog_runs b ON b.analysis_run_id=a.id WHERE b.id=%s AND b.project_id=%s",(backlog_id,project_id))
        source=cur.fetchone()
    try:
        metrics=evaluate(backlog,payload.expected_requirement_ids,source[0] if source else None)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("""INSERT INTO evaluation_runs(project_id,backlog_run_id,evaluator_id,metrics,golden)
                       VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                    (project_id,backlog_id,user['id'],Jsonb(metrics),Jsonb({'expected_requirement_ids':payload.expected_requirement_ids})))
        eval_id=cur.fetchone()[0]
    record_audit(user['id'],'evaluation.created','backlog',backlog_id,{'evaluation_id':str(eval_id)})
    return {'evaluation_id':str(eval_id),'metrics':metrics}

@router.get('/{project_id}/backlogs/{backlog_id}/evaluations')
def list_evaluations(project_id:UUID,backlog_id:UUID):
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("""SELECT e.id,e.metrics,e.created_at FROM evaluation_runs e
                       JOIN backlog_runs b ON b.id=e.backlog_run_id
                       WHERE b.project_id=%s AND b.id=%s ORDER BY e.created_at DESC LIMIT 30""",(project_id,backlog_id))
        rows=cur.fetchall()
    return [{'id':str(r[0]),'metrics':r[1],'created_at':r[2].isoformat()} for r in rows]
