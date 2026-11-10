from uuid import UUID
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from app.services.publishing_service import preview, publish, list_records, PublicationDenied, PublicationConflict
from integrations.publishing import PublishError
from app.services.auth_service import record_audit

router=APIRouter(prefix='/projects',tags=['Phase 5 Integrations'])

class PublishRequest(BaseModel):
    provider: str
    story_key: str
    dry_run: bool = True

@router.post('/{project_id}/backlogs/{backlog_id}/publish')
def publish_story(project_id:UUID,backlog_id:UUID,payload:PublishRequest,request:Request,x_reqflow_publish_key:str|None=Header(default=None)):
    if payload.provider not in ('jira','github'):raise HTTPException(422,'Choose jira or github.')
    if not payload.story_key or len(payload.story_key)>40:raise HTTPException(422,'Invalid story_key.')
    try:
        if payload.dry_run:
            return preview(project_id,backlog_id,payload.story_key,payload.provider)
        actor=request.state.user
        if actor['role'] not in ('admin','product_owner'):
            raise PublicationDenied('Live publishing requires admin or product_owner role')
        published=publish(project_id,backlog_id,payload.story_key,payload.provider,x_reqflow_publish_key)
        record_audit(actor['id'],'publication.created',payload.provider,backlog_id,{'story_key':payload.story_key,'external_url':published['external_url']})
        return published
    except PublicationDenied as exc:raise HTTPException(403,str(exc)) from exc
    except PublicationConflict as exc:raise HTTPException(409,str(exc)) from exc
    except PublishError as exc:raise HTTPException(422,str(exc)) from exc

@router.get('/{project_id}/backlogs/{backlog_id}/publications')
def publications(project_id:UUID,backlog_id:UUID):
    return list_records(project_id,backlog_id)
