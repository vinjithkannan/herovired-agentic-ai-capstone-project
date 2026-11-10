'''Phase 6.1: clarification decisions are separate from final story approval.'''
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb
from app.services.auth_service import require_roles, record_audit
from app.services.database import get_connection
from app.services.clarification_service import validate_proposal, apply_approved
from app.api.v1.backlog import _persist_backlog

router=APIRouter(prefix='/projects', tags=['Phase 6.1 Clarifications'])

class CriterionDraft(BaseModel):
    criterion_text: str
    test_type: str = 'functional'

class ClarificationDraft(BaseModel):
    title: str
    story_text: str
    rationale: str
    acceptance_criteria: list[CriterionDraft] = Field(min_length=1,max_length=12)

class Decision(BaseModel):
    approve: bool
    note: str = Field(min_length=10,max_length=2000)


def _source(cur,project_id,backlog_id,lock=False):
    cur.execute('''SELECT b.result,b.analysis_run_id,a.result FROM backlog_runs b
                   JOIN analysis_runs a ON a.id=b.analysis_run_id
                   WHERE b.id=%s AND b.project_id=%s'''+(' FOR UPDATE OF b' if lock else ''),
                   (backlog_id,project_id))
    row=cur.fetchone()
    if not row: raise HTTPException(404,'Backlog not found in project')
    return row

@router.get('/{project_id}/backlogs/{backlog_id}/clarifications')
def list_clarifications(project_id:UUID,backlog_id:UUID, user=Depends(require_roles('admin','product_owner','engineer','viewer'))):
    with get_connection() as conn,conn.cursor() as cur:
        _source(cur,project_id,backlog_id)
        cur.execute('''SELECT id,story_key,proposal,rationale,status,proposed_by,decided_by,decision_note,created_at,decided_at
                       FROM backlog_clarifications WHERE project_id=%s AND source_backlog_id=%s
                       ORDER BY created_at DESC''',(project_id,backlog_id))
        rows=cur.fetchall()
    return [dict(id=str(r[0]),story_key=r[1],proposal=r[2],rationale=r[3],status=r[4],
                 proposed_by=str(r[5]),decided_by=str(r[6]) if r[6] else None,
                 decision_note=r[7],created_at=r[8].isoformat(),decided_at=r[9].isoformat() if r[9] else None) for r in rows]

@router.post('/{project_id}/backlogs/{backlog_id}/stories/{story_key}/clarifications',status_code=201)
def propose(project_id:UUID,backlog_id:UUID,story_key:str,payload:ClarificationDraft,request:Request,
            user=Depends(require_roles('admin','product_owner','engineer'))):
    try: proposal=validate_proposal(payload.model_dump())
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    with get_connection() as conn,conn.cursor() as cur:
        original,_,_=_source(cur,project_id,backlog_id)
        if story_key not in {s['story_key'] for s in original.get('stories',[])}:
            raise HTTPException(404,'Unknown story key')
        cur.execute('''SELECT 1 FROM backlog_finalizations WHERE source_backlog_id=%s''',(backlog_id,))
        if cur.fetchone(): raise HTTPException(409,'This backlog has already been finalized')
        try:
            cur.execute('''INSERT INTO backlog_clarifications
                 (project_id,source_backlog_id,story_key,proposal,rationale,proposed_by)
                 VALUES (%s,%s,%s,%s,%s,%s) RETURNING id''',
                 (project_id,backlog_id,story_key,Jsonb(proposal),proposal['rationale'],user['id']))
        except Exception as exc:
            if getattr(exc,'sqlstate',None)=='23505':
                raise HTTPException(409,'Active clarification exists; decide it before proposing again') from exc
            raise
        clarification_id=cur.fetchone()[0]
    record_audit(user['id'],'clarification.proposed','clarification',str(clarification_id),
                 {'backlog_id':str(backlog_id),'story_key':story_key})
    return {'id':str(clarification_id),'status':'proposed','story_key':story_key}

@router.post('/{project_id}/backlogs/{backlog_id}/clarifications/{clarification_id}/decision')
def decide(project_id:UUID,backlog_id:UUID,clarification_id:UUID,payload:Decision,request:Request,
           user=Depends(require_roles('admin','product_owner'))):
    with get_connection() as conn,conn.cursor() as cur:
        _source(cur,project_id,backlog_id)
        cur.execute('''UPDATE backlog_clarifications SET status=%s,decision_note=%s,decided_by=%s,decided_at=NOW()
                       WHERE id=%s AND source_backlog_id=%s AND project_id=%s AND status='proposed'
                       RETURNING story_key,status''',
                       ('approved' if payload.approve else 'rejected',payload.note,user['id'],clarification_id,backlog_id,project_id))
        row=cur.fetchone()
    if not row: raise HTTPException(409,'Clarification missing or already decided')
    record_audit(user['id'],'clarification.decision','clarification',str(clarification_id),
                 {'backlog_id':str(backlog_id),'story_key':row[0],'status':row[1]})
    return {'id':str(clarification_id),'story_key':row[0],'status':row[1]}

@router.post('/{project_id}/backlogs/{backlog_id}/clarifications/{clarification_id}/supersede')
def supersede(project_id:UUID,backlog_id:UUID,clarification_id:UUID,payload:Decision,request:Request,
              user=Depends(require_roles('admin','product_owner'))):
    '''Invalidate an earlier approved decision while retaining its history.'''
    if payload.approve:
        raise HTTPException(422,'Use approve=false and document the reason to supersede')
    with get_connection() as conn,conn.cursor() as cur:
        _source(cur,project_id,backlog_id)
        cur.execute('SELECT 1 FROM backlog_finalizations WHERE source_backlog_id=%s',(backlog_id,))
        if cur.fetchone(): raise HTTPException(409,'Finalized version cannot be changed')
        cur.execute('''UPDATE backlog_clarifications
                       SET status='superseded',decision_note=%s,decided_by=%s,decided_at=NOW()
                       WHERE id=%s AND source_backlog_id=%s AND project_id=%s AND status='approved'
                       RETURNING story_key''', (payload.note,user['id'],clarification_id,backlog_id,project_id))
        row=cur.fetchone()
    if not row: raise HTTPException(409,'Approved clarification not found or already changed')
    record_audit(user['id'],'clarification.superseded','clarification',str(clarification_id),
                 {'story_key':row[0],'backlog_id':str(backlog_id)})
    return {'id':str(clarification_id),'status':'superseded','story_key':row[0]}

@router.get('/{project_id}/backlogs/{backlog_id}/clarifications/quality-preview')
def quality_preview(project_id:UUID,backlog_id:UUID,
                    user=Depends(require_roles('admin','product_owner','engineer','viewer'))):
    '''Read-only simulation using approved clarification proposals.'''
    with get_connection() as conn,conn.cursor() as cur:
        original,_,analysis=_source(cur,project_id,backlog_id)
        cur.execute('''SELECT story_key,proposal FROM backlog_clarifications
                       WHERE source_backlog_id=%s AND project_id=%s AND status='approved' ''',
                    (backlog_id,project_id))
        approvals=dict(cur.fetchall())
    evidence={r.get('temporary_id'):r.get('evidence_status') for r in analysis.get('validation',{}).get('requirements',[])}
    req_ids=set(original.get('source_requirement_ids',[]))
    requirements=[r for r in analysis.get('requirements',[]) if r.get('temporary_id') in req_ids and evidence.get(r.get('temporary_id')) in ('supported','partially_supported')]
    try: revised=apply_approved(original,approvals,requirements,evidence)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    clearances=revised['story_clearances']
    return {'approved_clarifications':len(approvals),'quality_cleared':sum(v['status']=='quality_cleared' for v in clearances.values()),
            'total_stories':len(clearances),'ready_to_finalize':bool(approvals) and all(v['status']=='quality_cleared' for v in clearances.values()),
            'story_clearances':clearances,'validation':revised['validation']}

@router.post('/{project_id}/backlogs/{backlog_id}/clarifications/finalize',status_code=201)
def finalize(project_id:UUID,backlog_id:UUID,request:Request,user=Depends(require_roles('admin','product_owner'))):
    # One transaction locks source backlog, computes quality, saves normalized snapshot
    # and records version lineage. Concurrent finalization is prevented by row lock.
    with get_connection() as conn,conn.cursor() as cur:
        original,analysis_id,analysis=_source(cur,project_id,backlog_id,lock=True)
        cur.execute('SELECT new_backlog_id FROM backlog_finalizations WHERE source_backlog_id=%s',(backlog_id,))
        if cur.fetchone(): raise HTTPException(409,'Backlog already finalized; load its revision')
        cur.execute('''SELECT id,story_key,proposal FROM backlog_clarifications
                       WHERE source_backlog_id=%s AND project_id=%s AND status='approved' ORDER BY created_at''',
                       (backlog_id,project_id))
        rows=cur.fetchall()
        if not rows: raise HTTPException(409,'No approved clarification decisions')
        approvals={r[1]:r[2] for r in rows}
        if len(approvals)!=len(rows): raise HTTPException(409,'Multiple approved decisions for one story')
        validation=analysis.get('validation',{}).get('requirements',[])
        evidence={r.get('temporary_id'):r.get('evidence_status') for r in validation}
        supported=set(original.get('source_requirement_ids',[]))
        requirements=[r for r in analysis.get('requirements',[]) if r.get('temporary_id') in supported and evidence.get(r.get('temporary_id')) in ('supported','partially_supported')]
        try: revised=apply_approved(original,approvals,requirements,evidence)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
        # Prevent publishing or misleading a fully cleared status when any review is outstanding.
        uncleared={k:v['status'] for k,v in revised['story_clearances'].items() if v['status']!='quality_cleared'}
        if uncleared: raise HTTPException(409,{'message':'Clarifications incomplete or validation still failing','uncleared':uncleared,
                  'issues':revised['validation']['issues']})
        revised['finalization_of_backlog_id']=str(backlog_id)
        revised['clarification_ids']=[str(r[0]) for r in rows]
        revised['clarification_audit']={'reviewed_by':user['username'],'approved_count':len(rows)}
        revised.pop('backlog_id',None); revised.pop('created_at',None)
        revised.pop('story_clearances',None)  # computed fresh on GET
        # Atomic normalized snapshot insert, in the SAME transaction.
        # _persist_backlog normally opens its own connection; use a cursor-aware insert here.
        from app.services.clarification_persistence import insert_revision
        new_id, created_at=insert_revision(cur,project_id,analysis_id,revised)
        cur.execute('''INSERT INTO backlog_finalizations(source_backlog_id,new_backlog_id,actor_id,clarification_ids,quality_summary)
                       VALUES (%s,%s,%s,%s,%s)''',(backlog_id,new_id,user['id'],Jsonb([str(r[0]) for r in rows]),Jsonb(revised['validation'])))
        cur.execute('''INSERT INTO security_audit(actor_id,event,object_type,object_id,detail)
                       VALUES (%s,%s,%s,%s,%s)''',
                    (user['id'],'backlog.finalized','backlog',str(new_id),Jsonb({'source_backlog_id':str(backlog_id),'clarification_ids':[str(r[0]) for r in rows]})))
    return {'backlog_id':str(new_id),'created_at':created_at.isoformat(),
            'source_backlog_id':str(backlog_id),'quality_status':'quality_cleared',
            'approved_clarifications':len(rows),'approvals':'pending'}
