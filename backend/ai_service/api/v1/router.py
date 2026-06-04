from fastapi import APIRouter, Depends

from backend.ai_service.api.v1.routes import ask, health, metadata, policies, sql, workflows
from backend.ai_service.security.jwt_auth import require_authenticated_user, require_staff_user

api_router = APIRouter()
ProtectedDependency = Depends(require_authenticated_user)
protected_dependencies = [ProtectedDependency]
StaffDependency = Depends(require_staff_user)
staff_dependencies = [StaffDependency]

api_router.include_router(
    ask.router,
    prefix="/ask",
    tags=["ask"],
)
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(
    metadata.router,
    prefix="/metadata",
    tags=["metadata"],
    dependencies=staff_dependencies,
)
api_router.include_router(
    sql.router,
    prefix="/sql",
    tags=["sql"],
    dependencies=staff_dependencies,
)
api_router.include_router(
    policies.router,
    prefix="/policies",
    tags=["policies"],
    dependencies=staff_dependencies,
)
api_router.include_router(
    workflows.router,
    prefix="/workflows",
    tags=["workflows"],
    dependencies=protected_dependencies,
)
