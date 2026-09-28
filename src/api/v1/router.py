"""API v1 router aggregator."""

from fastapi import APIRouter

from src.api.dependencies import SettingsDep
from src.api.v1.auth import router as auth_router
from src.api.v1.compliance import router as compliance_router
from src.api.v1.dashboard import router as dashboard_router
from src.api.v1.evidence import router as evidence_router
from src.api.v1.frameworks import router as frameworks_router
from src.api.v1.gap_reports import router as gap_reports_router
from src.api.v1.matching import router as matching_router

api_v1_router = APIRouter(prefix="/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(frameworks_router)
api_v1_router.include_router(evidence_router)
api_v1_router.include_router(matching_router)
api_v1_router.include_router(compliance_router)
api_v1_router.include_router(gap_reports_router)
api_v1_router.include_router(dashboard_router)


@api_v1_router.get("/health", tags=["Health"])
async def v1_health_check(settings: SettingsDep) -> dict[str, str]:
    """API v1 health status endpoint."""
    return {
        "status": "healthy",
        "api_version": "v1",
        "app_env": settings.app_env,
        "ai_mock_mode": str(settings.ai_mock_mode).lower(),
    }
