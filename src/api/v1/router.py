"""API v1 router aggregator."""

from fastapi import APIRouter

from src.api.dependencies import CurrentUserDep, SettingsDep

api_v1_router = APIRouter(prefix="/v1")


@api_v1_router.get("/health", tags=["Health"])
async def v1_health_check(settings: SettingsDep) -> dict[str, str]:
    """API v1 health status endpoint."""
    return {
        "status": "healthy",
        "api_version": "v1",
        "app_env": settings.app_env,
        "ai_mock_mode": str(settings.ai_mock_mode).lower(),
    }


@api_v1_router.get("/auth/me", tags=["Authentication"])
async def get_current_user_profile(current_user: CurrentUserDep) -> dict:
    """Return profile and role of authenticated caller."""
    return {
        "user_id": str(current_user.user_id),
        "username": current_user.username,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
    }
