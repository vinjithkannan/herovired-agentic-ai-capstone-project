from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.system import router as system_router
from app.api.v1.documents import router as documents_router
from app.api.v1.analysis import router as analysis_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Agentic AI platform for converting business requirements into sprint-ready delivery artifacts.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(system_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "reqflow-api"}

@app.get("/", tags=["Root"])
async def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/health"}
