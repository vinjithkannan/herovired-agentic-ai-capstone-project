"""Human-gated Phase 7 delivery artifacts: scoped by project and immutable backlog."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb
from app.services.database import get_connection
from app.services.auth_service import require_roles, record_audit
from app.api.v1.backlog import get_backlog
from agents.orchestrator.graph import workflow_graph

router = APIRouter(prefix='/projects', tags=['Phase 7 Solution Design & Delivery Plan'])

class ApprovalDecision(BaseModel):
    approve: bool
    note: str = Field(min_length=10, max_length=2000)


def _load(project_id, backlog_id):
    backlog = get_backlog(project_id, backlog_id)  # recomputes source-backed quality clearance
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('''SELECT p.name,a.result FROM backlog_runs b
                       JOIN projects p ON p.id=b.project_id
                       JOIN analysis_runs a ON a.id=b.analysis_run_id
                       WHERE b.id=%s AND b.project_id=%s''',(backlog_id,project_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404,'Backlog not found')
        cur.execute('''SELECT kind,artifact,status FROM delivery_artifacts
                       WHERE project_id=%s AND backlog_run_id=%s''',(project_id,backlog_id))
        prior = {r[0]: {'artifact':r[1], 'status':r[2]} for r in cur.fetchall()}
    project_name, analysis = row
    evidence = {r.get('temporary_id'):r.get('evidence_status')
                for r in analysis.get('validation',{}).get('requirements',[])}
    return backlog, analysis, evidence, project_name, prior


def _run(project_id, backlog_id, prior):
    backlog, analysis, evidence, name, _ = _load(project_id, backlog_id)
    state = {
        'project_id':str(project_id), 'backlog_id':str(backlog_id),
        'project_title': name,
        'source_requirement_ids':backlog.get('source_requirement_ids',[]),
        'requirements':analysis.get('requirements',[]), 'evidence':evidence,
        'stories':backlog.get('stories',[]),
        'story_clearances':backlog.get('story_clearances',{}),
        'acceptance_criteria':backlog.get('acceptance_criteria',[]),
        'dependencies':backlog.get('dependencies',[]),
        'design_approval': prior.get('design',{}).get('status','draft'),
        'plan_approval': prior.get('plan',{}).get('status','draft'),
    }
    try:
        output = workflow_graph.invoke(state)
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc
    return output


def _ensure_scope(current, previous):
    old = previous.get('scope',{}).get('story_keys',[])
    new = current.get('scope',{}).get('story_keys',[])
    if sorted(old) != sorted(new):
        raise HTTPException(409,'Story approvals or quality clearances have changed. The existing design is stale; a new review is required.')


@router.get('/{project_id}/backlogs/{backlog_id}/delivery')
def view_delivery(project_id:UUID,backlog_id:UUID,
                  user=Depends(require_roles('admin','product_owner','engineer','viewer'))):
    _,_,_,_,prior = _load(project_id,backlog_id)
    return {'project_id':str(project_id),'backlog_id':str(backlog_id),'artifacts':prior}


@router.post('/{project_id}/backlogs/{backlog_id}/delivery/design',status_code=201)
def generate_design(project_id:UUID,backlog_id:UUID,request:Request,
                    user=Depends(require_roles('admin','product_owner','engineer'))):
    _,_,_,_,prior = _load(project_id,backlog_id)
    if prior.get('design',{}).get('status') == 'approved':
        raise HTTPException(409,'Design already approved. Preserve the approved artifact; use a new backlog for changed scope.')
    if 'plan' in prior:
        raise HTTPException(409,'Planning already exists; do not invalidate its traceability.')
    output = _run(project_id,backlog_id,{})
    design = output['solution_design']
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO delivery_artifacts(project_id,backlog_run_id,kind,artifact)
                       VALUES (%s,%s,'design',%s)
                       ON CONFLICT (backlog_run_id,kind) DO UPDATE
                       SET artifact=EXCLUDED.artifact,status='draft',decided_by=NULL,
                           decided_at=NULL,decision_note=NULL
                       WHERE delivery_artifacts.status <> 'approved'
                       RETURNING id''', (project_id,backlog_id,Jsonb(design)))
        row = cur.fetchone()
        if not row:
            raise HTTPException(409,'Approved design cannot be overwritten')
    record_audit(user['id'],'delivery.design.generated','delivery',str(row[0]),{'backlog_id':str(backlog_id)})
    return {'status':'awaiting_design_approval','artifact':design,'execution_log':output['execution_log']}


@router.post('/{project_id}/backlogs/{backlog_id}/delivery/design/approval')
def approve_design(project_id:UUID,backlog_id:UUID,payload:ApprovalDecision,request:Request,
                   user=Depends(require_roles('admin','product_owner'))):
    _,_,_,_,prior = _load(project_id,backlog_id)
    current = prior.get('design')
    if not current or current['status'] != 'draft':
        raise HTTPException(409,'No draft design awaiting approval')
    candidate = _run(project_id,backlog_id,{})['solution_design']
    _ensure_scope(candidate,current['artifact'])
    status='approved' if payload.approve else 'rejected'
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute('''UPDATE delivery_artifacts SET status=%s,decided_by=%s,
                       decision_note=%s,decided_at=NOW()
                       WHERE project_id=%s AND backlog_run_id=%s AND kind='design'
                         AND status='draft' RETURNING id''',
                    (status,user['id'],payload.note,project_id,backlog_id))
        row=cur.fetchone()
        if not row: raise HTTPException(409,'Design decision already made')
    record_audit(user['id'],'delivery.design.decision','delivery',str(row[0]),{'status':status})
    return {'kind':'design','status':status}


@router.post('/{project_id}/backlogs/{backlog_id}/delivery/plan',status_code=201)
def generate_plan(project_id:UUID,backlog_id:UUID,request:Request,
                  user=Depends(require_roles('admin','product_owner','engineer'))):
    _,_,_,_,prior = _load(project_id,backlog_id)
    if prior.get('design',{}).get('status') != 'approved':
        raise HTTPException(409,'Product Owner must approve the solution design first')
    if 'plan' in prior:
        raise HTTPException(409,'Plan already exists for this backlog')
    output=_run(project_id,backlog_id,prior)
    _ensure_scope(output['solution_design'], prior['design']['artifact'])
    plan={'status':'draft_requires_human_review',
          'design_backlog_id':str(backlog_id),
          'story_keys':[s['story_key'] for s in output['eligible_stories']],
          'tasks':output['implementation_tasks'],
          'assumptions':['All estimates are provisional, not delivery commitments.',
                         'Approve task dependencies, capacity and estimates during team planning.']}
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute('''INSERT INTO delivery_artifacts(project_id,backlog_run_id,kind,artifact)
                       VALUES (%s,%s,'plan',%s) RETURNING id''',
                    (project_id,backlog_id,Jsonb(plan)))
        row=cur.fetchone()
    record_audit(user['id'],'delivery.plan.generated','delivery',str(row[0]),{'backlog_id':str(backlog_id)})
    return {'status':'awaiting_plan_approval','artifact':plan,'execution_log':output['execution_log']}


@router.post('/{project_id}/backlogs/{backlog_id}/delivery/plan/approval')
def approve_plan(project_id:UUID,backlog_id:UUID,payload:ApprovalDecision,request:Request,
                 user=Depends(require_roles('admin','product_owner'))):
    _,_,_,_,prior = _load(project_id,backlog_id)
    if prior.get('design',{}).get('status') != 'approved' or prior.get('plan',{}).get('status') != 'draft':
        raise HTTPException(409,'Approved design and draft plan are required')
    output=_run(project_id,backlog_id,prior)
    _ensure_scope(output['solution_design'],prior['design']['artifact'])
    if sorted(prior['plan']['artifact'].get('story_keys',[])) != sorted(s['story_key'] for s in output['eligible_stories']):
        raise HTTPException(409,'Story eligibility changed; do not approve a stale plan')
    status='approved' if payload.approve else 'rejected'
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute('''UPDATE delivery_artifacts SET status=%s,decided_by=%s,decision_note=%s,
                       decided_at=NOW() WHERE project_id=%s AND backlog_run_id=%s
                       AND kind='plan' AND status='draft' RETURNING id''',
                    (status,user['id'],payload.note,project_id,backlog_id))
        row=cur.fetchone()
        if not row: raise HTTPException(409,'Plan decision already made')
    record_audit(user['id'],'delivery.plan.decision','delivery',str(row[0]),{'status':status})
    return {'kind':'plan','status':status,'workflow_status':'ready_for_delivery' if payload.approve else 'plan_rejected'}


@router.get('/{project_id}/backlogs/{backlog_id}/delivery/design.md',response_class=PlainTextResponse)
def export_design(project_id:UUID,backlog_id:UUID,
                  user=Depends(require_roles('admin','product_owner','engineer','viewer'))):
    _,_,_,_,prior=_load(project_id,backlog_id)
    if 'design' not in prior: raise HTTPException(404,'Design has not been generated')
    design=prior['design']['artifact']
    lines=[f"# {design['title']}", '', f"Approval: {prior['design']['status']}", '',
           '## Scope', ', '.join(design['scope']['story_keys']), '',
           '## Architecture', ' → '.join(design['architecture']['flow']), '',
           '## Components']
    lines += [f"- **{c['name']}**: {c['responsibility']}" for c in design['components']]
    lines += ['', '## Proposed APIs']
    lines += [f"- {c['story_key']}: {c['purpose']} ({c['operation']})" for c in design['api_proposals']]
    lines += ['', '## Proposed data model']
    lines += [f"- {e['entity']}: {', '.join(e['fields'])} — {e['status']}" for e in design['data_model_proposals']]
    lines += ['', '## Assumptions and open decisions']
    lines += ['- '+a for a in design['assumptions']+design['open_decisions']]
    return '\n'.join(lines)+'\n'
