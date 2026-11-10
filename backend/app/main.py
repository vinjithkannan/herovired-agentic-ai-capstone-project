from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from time import perf_counter
import logging
from app.services.auth_service import resolve_bearer
from app.services.observability import observe
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.auth import router as auth_router
from app.api.v1.operations import router as operations_router
from app.api.v1.evaluation import router as evaluation_router
from app.api.v1.reconciliation import router as reconciliation_router
from app.api.v1.system import router as system_router
from app.api.v1.documents import router as documents_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.backlog import router as backlog_router
from app.api.v1.clarifications import router as clarification_router
from app.api.v1.publishing import router as publishing_router
from app.api.v1.delivery import router as delivery_router
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
app.include_router(auth_router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1")
app.include_router(evaluation_router, prefix="/api/v1")
app.include_router(reconciliation_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(backlog_router, prefix="/api/v1")
app.include_router(clarification_router, prefix="/api/v1")
app.include_router(publishing_router, prefix="/api/v1")
app.include_router(delivery_router, prefix="/api/v1")

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "reqflow-api"}

@app.get("/", tags=["Root"])
async def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/health"}


# Swagger/OpenAPI security declaration. Actual authorization remains enforced by
# security_and_metrics middleware and role checks on protected routes.
def custom_openapi():
    if app.openapi_schema is not None:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schemes = schema.setdefault('components', {}).setdefault('securitySchemes', {})
    schemes['BearerAuth'] = {
        'type': 'http',
        'scheme': 'bearer',
        'bearerFormat': 'opaque',
        'description': 'Use access_token from POST /api/v1/auth/login (no Bearer prefix).',
    }

    public_paths = {'/health', '/', '/api/v1/auth/login'}
    http_methods = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}
    for path, item in schema.get('paths', {}).items():
        if path in public_paths or not path.startswith('/api/v1/'):
            continue
        for method, operation in item.items():
            if method.lower() in http_methods and isinstance(operation, dict):
                # Keep the existing endpoint-specific security requirements if any.
                # All protected ReqFlow APIs should use the same BearerAuth scheme.
                security = operation.setdefault('security', [])
                if {'BearerAuth': []} not in security:
                    security.append({'BearerAuth': []})

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi

PUBLIC_PATHS={'/health','/','/openapi.json','/docs','/redoc','/api/v1/auth/login'}


def required_role_for(request):
    """Minimum authorization for every API mutation (path based, no request body consumption).
    Local admin can perform all roles. Publishing endpoint checks live/dry-run separately.
    """
    if request.method in ('GET','HEAD','OPTIONS'):
        return {'admin','product_owner','engineer','viewer'}
    path=request.url.path
    if path == '/api/v1/auth/logout':
        return {'admin','product_owner','engineer','viewer'}
    if '/publications/reconcile' in path:
        return {'admin'}
    if path.endswith('/publish'):
        return {'admin','product_owner','engineer','viewer'}
    if path.endswith('/approval') and request.method=='PATCH':
        return {'admin','product_owner'}
    if '/delivery/' in path:
        if path.endswith('/approval'):
            return {'admin','product_owner'}
        return {'admin','product_owner','engineer'}
    if '/clarifications/' in path or path.endswith('/clarifications'):
        if request.method=='POST':
            if path.endswith('/decision') or path.endswith('/finalize') or path.endswith('/supersede'):
                return {'admin','product_owner'}
            return {'admin','product_owner','engineer'}
    if path.endswith('/evaluate'):
        return {'admin','product_owner','engineer'}
    if request.method=='POST' and ('/documents' in path or path.endswith('/analyze') or '/backlogs/' in path or path.endswith('/backlogs/generate') or path.endswith('/rag/search') or path.endswith('/projects')):
        return {'admin','engineer'}
    return {'admin'}

@app.middleware('http')
async def security_and_metrics(request:Request,call_next):
    started=perf_counter()
    path=request.url.path
    user=None
    status=500
    try:
        if request.method != 'OPTIONS' and path.startswith('/api/v1/') and path not in PUBLIC_PATHS:
            user=resolve_bearer(request.headers.get('authorization'))
            if user is None:
                status=401
                return JSONResponse(status_code=401,content={'detail':'Bearer login required'})
            request.state.user=user
            if user['role'] not in required_role_for(request):
                status=403
                return JSONResponse(status_code=403,content={'detail':'Insufficient role'})
        response=await call_next(request)
        status=response.status_code
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response
    finally:
        # Avoid path cardinality/identifiers: use static path categorization. No raw IDs/tokens.
        if path.startswith('/api/v1/'):
            if path.endswith('/analyze'): route='requirements.analyze'
            elif path.endswith('/backlogs/generate'): route='backlog.generate'
            elif path.endswith('/repair'): route='backlog.repair'
            elif path.endswith('/publish'): route='external.publish_or_preview'
            elif path.endswith('/evaluate'): route='evaluation.run'
            elif path.endswith('/publications/reconcile'): route='publication.reconcile'
            elif path.endswith('/publications/retry'): route='publication.retry'
            elif path.endswith('/rag/search'): route='rag.search'
            elif '/documents' in path: route='documents'
            elif '/backlogs' in path: route='backlog.read_or_approval'
            else: route='api.' + path.split('/api/v1/',1)[1].split('/',1)[0]
        else:
            route='non-api' 
        observe(route,request.method,status,perf_counter()-started)
