'''Actual MCP stdio server. Start inside backend container:
python -m mcp_servers.publishing_server
Client must hold a publishing key for live actions, provided as tool argument.
'''
from mcp.server.fastmcp import FastMCP
from app.services.publishing_service import preview, publish, list_records
from uuid import UUID
import os

def require_local_mcp():
    if os.getenv("PHASE6_ENABLE_TRUSTED_MCP", "false").lower() != "true":
        raise PermissionError("MCP direct service access disabled by default. Use authenticated FastAPI, or explicitly enable only within a trusted local process.")

mcp=FastMCP('reqflow-phase5-publishing')

@mcp.tool()
def preview_quality_cleared_story(project_id:str,backlog_id:str,story_key:str,provider:str)->dict:
    '''Preview a quality-cleared story, including one with pending manual approval. Never writes remotely.'''
    require_local_mcp()
    return preview(UUID(project_id),UUID(backlog_id),story_key,provider)

@mcp.tool()
def publish_approved_story(project_id:str,backlog_id:str,story_key:str,provider:str,publishing_key:str)->dict:
    '''Publish only an approved and quality-cleared story. Explicit publishing_key required.'''
    require_local_mcp()
    if os.getenv("PHASE6_TRUSTED_MCP_LIVE", "false").lower() != "true":
        raise PermissionError("MCP live publishing disabled; no per-user identity available")
    return publish(UUID(project_id),UUID(backlog_id),story_key,provider,publishing_key)

@mcp.tool()
def list_story_publications(project_id:str,backlog_id:str)->list[dict]:
    '''List synchronization attempts and remote references for a saved backlog.'''
    require_local_mcp()
    return list_records(UUID(project_id),UUID(backlog_id))

if __name__=='__main__':
    mcp.run(transport='stdio')
