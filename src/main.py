"""FastAPI main application entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.v1.router import api_v1_router
from src.config import get_settings
from src.core.exceptions import (
    AIProviderException,
    AuthenticationException,
    ComplianceException,
    DuplicateEntityException,
    EntityNotFoundException,
    ValidationException,
)
from src.core.logging import configure_logging, get_logger

logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle management."""
    settings = get_settings()
    configure_logging(level=10 if settings.debug else 20)
    logger.info("Initializing %s in [%s] mode...", settings.app_name, settings.app_env)
    logger.info("Database URL configured: %s", settings.effective_database_url.split("@")[-1])
    logger.info("Storage directory: %s", settings.storage_dir.resolve())
    logger.info("AI Mock Mode: %s (Application LLM: %s)", settings.ai_mock_mode, settings.xai_model)

    # Ensure storage directory exists
    settings.storage_dir.mkdir(parents=True, exist_ok=True)

    yield

    logger.info("Shutting down %s...", settings.app_name)


def create_application() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="AI-powered compliance checklist automation agent for evidence matching, gap detection, and compliance status tracking.",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount v1 router
    app.include_router(api_v1_router, prefix="/api")

    # Domain exception → HTTP status mapping
    _exception_status_map: dict[type, int] = {
        AuthenticationException: status.HTTP_401_UNAUTHORIZED,
        EntityNotFoundException: status.HTTP_404_NOT_FOUND,
        DuplicateEntityException: status.HTTP_409_CONFLICT,
        ValidationException: 422,
        AIProviderException: status.HTTP_502_BAD_GATEWAY,
    }

    @app.exception_handler(ComplianceException)
    async def compliance_exception_handler(request: Request, exc: ComplianceException) -> JSONResponse:
        http_status = _exception_status_map.get(type(exc), status.HTTP_400_BAD_REQUEST)
        logger.error("Domain exception [%d]: %s | details: %s", http_status, exc.message, exc.details)
        return JSONResponse(
            status_code=http_status,
            content={"error": exc.__class__.__name__, "message": exc.message, "details": exc.details},
        )

    # Root health check endpoint
    @app.get("/health", tags=["Health"])
    async def root_health() -> dict[str, str]:
        return {
            "status": "healthy",
            "service": settings.app_name,
            "environment": settings.app_env,
        }

    return app


app = create_application()
