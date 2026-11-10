from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer

from app.services.auth_service import require_roles
from app.services.observability import snapshot

router = APIRouter(
    prefix="/operations",
    tags=["Phase 6 Observability"]
)

# Declare Bearer authentication in OpenAPI / Swagger.
bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    description="Enter the access_token returned by POST /api/v1/auth/login",
    auto_error=False,
)


@router.get(
    "/metrics",
    dependencies=[Depends(bearer_scheme)],
)
def metrics(user=Depends(require_roles("admin"))):
    return {
        "scope": "current_uvicorn_worker",
        "requests": snapshot(),
        "latency_bucket_bounds_seconds": [
            0.1, 0.5, 1, 5, 30, 120
        ],
    }