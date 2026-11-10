from fastapi import APIRouter

router = APIRouter()

@router.get("/system/info", tags=["System"])
async def system_info():
    return {
        "application": "ReqFlow AI",
        "phase": 6,
        "components": {
            "api": "ready",
            "database": "configured",
            "vector_store": "pgvector initialized by Docker",
            "agent_orchestrator": "LangGraph requirements analysis",
            "llm": "Ollama local inference",
            "mcp": "Phase 6 trusted local mode only; disabled by default"
        }
    }
