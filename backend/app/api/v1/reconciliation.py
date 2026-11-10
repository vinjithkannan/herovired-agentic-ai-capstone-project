"""Explicit human-authorized reconciliation; never silently re-POST.
A failed reservation remains as audit evidence and is deliberately re-armed separately.
"""
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from psycopg.types.json import Jsonb
from app.services.auth_service import require_roles, record_audit
from app.services.database import get_connection
from app.services.publishing_service import provider_config, require_live_key, read_snapshot
from integrations.publishing import publish_provider, validate_target
import httpx
import logging
logger=logging.getLogger(__name__)
from app.services.publication_reconciliation import scan,ReconciliationError

router=APIRouter(prefix='/projects',tags=['Phase 6 Publication Recovery'])
class ReconcileRequest(BaseModel):
    publication_id: UUID
    confirm_absence: bool=False

@router.post('/{project_id}/backlogs/{backlog_id}/publications/reconcile')
def reconcile(project_id:UUID,backlog_id:UUID,payload:ReconcileRequest,user=Depends(require_roles('admin'))):
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("""SELECT story_key,provider,target,state FROM external_publications
                       WHERE id=%s AND project_id=%s AND backlog_run_id=%s""",(payload.publication_id,project_id,backlog_id))
        row=cur.fetchone()
    if not row:raise HTTPException(404,'Publication not found')
    story_key,provider,target,state=row
    if state not in ('uncertain','failed'):
        raise HTTPException(409,'Only uncertain or failed publications can be reconciled')
    config=provider_config()
    if validate_target(provider,config) != target:
        raise HTTPException(409,'Configured remote target differs from saved publication target; use the original target for reconciliation.')
    try:
        result=scan(provider,config,project_id,backlog_id,story_key)
    except ReconciliationError as exc:
        raise HTTPException(503,str(exc)) from exc
    matches=result['matches']
    if len(matches)>1:raise HTTPException(409,'Multiple exact marker matches; manual reconciliation required')
    if matches:
        m=matches[0]
        with get_connection() as conn,conn.cursor() as cur:
            cur.execute("""UPDATE external_publications SET state='published',external_id=%s,external_url=%s,
                           error_note=NULL,updated_at=NOW() WHERE id=%s AND state IN ('uncertain','failed')""",
                        (m['external_id'],m['external_url'],payload.publication_id))
            cur.execute('INSERT INTO publication_recovery_audit(publication_id,actor_id,action,evidence) VALUES (%s,%s,%s,%s)',
                        (payload.publication_id,user['id'],'linked_existing',Jsonb(result)))
        return {'state':'published','match':m}
    if not payload.confirm_absence:
        return {'state':state,'remote_matches':0,'scan_complete':True,'action':'Confirm absence explicitly to mark failed'}
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("""UPDATE external_publications SET state='failed',error_note='No exact remote marker found in complete scan; requires authorized retry',updated_at=NOW()
                       WHERE id=%s AND state='uncertain' RETURNING id""",(payload.publication_id,))
        changed=cur.fetchone()
        cur.execute('INSERT INTO publication_recovery_audit(publication_id,actor_id,action,evidence) VALUES (%s,%s,%s,%s)',
                    (payload.publication_id,user['id'],'absence_verified' if changed else 'absence_rechecked',Jsonb(result)))
    return {'state':'failed','scan_complete':True,'action':'Reservation retained; use authorized retry only after checking provider permissions'}

class RetryRequest(BaseModel):
    publication_id:UUID
    publish_key:str

@router.post('/{project_id}/backlogs/{backlog_id}/publications/retry')
def retry_verified_absence(project_id:UUID,backlog_id:UUID,payload:RetryRequest,
                           user=Depends(require_roles('admin'))):
    """One explicit admin retry after complete fresh scan; no blind retries.
    Only row state=failed (already reconciled) can be re-armed, idempotent row retained.
    """
    from app.services.publishing_service import PublicationDenied
    try:
        require_live_key(payload.publish_key)
        with get_connection() as conn,conn.cursor() as cur:
            cur.execute("""SELECT story_key,provider,target,state FROM external_publications
                           WHERE id=%s AND project_id=%s AND backlog_run_id=%s""",
                        (payload.publication_id,project_id,backlog_id))
            row=cur.fetchone()
        if not row or row[3]!='failed':
            raise HTTPException(409,'Only previously reconciled failed publications may be retried')
        story_key,provider,target,_=row
        backlog,story=read_snapshot(project_id,backlog_id,story_key,live=True)
        config=provider_config()
        if validate_target(provider,config) != target:
            raise HTTPException(409,'Configured provider target differs from saved reservation')
        if provider not in ('jira','github'):
            raise HTTPException(422,'Unsupported provider')
        # Re-check remote just before any write. Never infer absence from an incomplete scan.
        result=scan(provider,config,project_id,backlog_id,story_key)
        if result['matches']:
            raise HTTPException(409,'Matching remote issue found; reconcile it instead of retrying')
    except PublicationDenied as exc:
        raise HTTPException(403,str(exc)) from exc
    except ReconciliationError as exc:
        raise HTTPException(503,str(exc)) from exc
    # One and only one worker may reserve this attempt.
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("""UPDATE external_publications SET state='reserved',error_note=NULL,updated_at=NOW()
                       WHERE id=%s AND state='failed' RETURNING id""",(payload.publication_id,))
        if not cur.fetchone():
            raise HTTPException(409,'Retry concurrently reserved')
        cur.execute('INSERT INTO publication_recovery_audit(publication_id,actor_id,action,evidence) VALUES (%s,%s,%s,%s)',
                    (payload.publication_id,user['id'],'retry_reserved',Jsonb(result)))
    try:
        published=publish_provider(provider,config,story,backlog.get('acceptance_criteria',[]),str(project_id),str(backlog_id))
    except Exception as exc:
        status=None
        if isinstance(exc,httpx.HTTPStatusError):
            status=exc.response.status_code
        logger.error('External retry failed: provider=%s story=%s http_status=%s exception=%s',
                     provider,story_key,status,type(exc).__name__)
        note=(f'Remote API HTTP {status}; inspect provider response' if status else 'Remote outcome uncertain; inspect provider')
        with get_connection() as conn,conn.cursor() as cur:
            cur.execute("UPDATE external_publications SET state='uncertain',error_note=%s,updated_at=NOW() WHERE id=%s",(note,payload.publication_id))
        raise HTTPException(409,'Retry failed or outcome uncertain. Reconcile before another attempt.') from exc
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("""UPDATE external_publications SET state='published', external_id=%s,external_url=%s,
                       error_note=NULL,updated_at=NOW() WHERE id=%s""",
                    (published['external_id'],published['external_url'],payload.publication_id))
        cur.execute('INSERT INTO publication_recovery_audit(publication_id,actor_id,action,evidence) VALUES (%s,%s,%s,%s)',
                    (payload.publication_id,user['id'],'retry_published',Jsonb({'external_id':published['external_id']})))
    return {'state':'published','external_id':published['external_id'],'external_url':published['external_url']}
