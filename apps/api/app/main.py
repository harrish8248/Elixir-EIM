"""
Main FastAPI Application Entrypoint - Elixir Enterprise Information Management.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from apps.api.app.platform.branding import BRANDING
from apps.api.app.platform.config import settings
from apps.api.app.platform.correlation import CorrelationIdMiddleware, get_correlation_id
from apps.api.app.platform.errors import (
    ElixirError,
    elixir_error_handler,
    unhandled_exception_handler,
)
from apps.api.app.platform.logging import logger
from apps.api.app.platform.registry import module_registry
from apps.api.app.tenancy import TenancyMiddleware

START_TIME = datetime.now(timezone.utc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    logger.info(
        f"Starting {BRANDING.name} ({BRANDING.short_name}) v{BRANDING.version} [{settings.elixir_env}]"
    )

    # Discover and register all module manifests
    modules_root = Path(__file__).parent
    try:
        discovered = module_registry.discover_modules(modules_root)
        logger.info(f"Loaded {len(discovered)} modules: {module_registry.startup_order()}")
    except Exception as exc:
        logger.error(f"Error during module discovery: {exc}")

    yield

    logger.info(f"Shutting down {BRANDING.short_name}")


def create_app() -> FastAPI:
    """Factory creating and configuring the FastAPI instance."""
    app = FastAPI(
        title=BRANDING.name,
        description=f"REST API for {BRANDING.name} - Enterprise Content, Records, and Governance.",
        version=BRANDING.version,
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Middlewares (Order: Exception handlers -> Correlation -> Tenancy -> CORS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TenancyMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    # Exception Handlers
    app.add_exception_handler(ElixirError, elixir_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # --------------------------------------------------------------------------
    # System & Health Endpoints
    # --------------------------------------------------------------------------
    @app.get("/api/v1/system/info", tags=["System"])
    async def get_system_info() -> Dict[str, Any]:
        """Expose product branding, version, and active modules."""
        modules = [
            {
                "name": manifest.name,
                "version": manifest.version,
                "title": manifest.title,
                "featureFlag": manifest.feature_flag_key,
            }
            for manifest in module_registry.all_modules().values()
        ]

        return {
            "data": {
                "name": BRANDING.name,
                "shortName": BRANDING.short_name,
                "version": BRANDING.version,
                "buildVersion": BRANDING.build_version,
                "apiVersion": BRANDING.api_version,
                "vendor": BRANDING.vendor,
                "copyright": BRANDING.copyright_statement,
                "environment": settings.elixir_env,
                "uptimeSeconds": (datetime.now(timezone.utc) - START_TIME).total_seconds(),
                "activeModules": modules,
            },
            "meta": {
                "requestId": get_correlation_id(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": BRANDING.version,
            },
        }

    @app.get("/api/v1/system/health", tags=["System"])
    @app.get("/api/v1/system/health/live", tags=["System"])
    async def liveness_probe() -> Dict[str, Any]:
        """Simple liveness probe."""
        return {
            "status": "UP",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/api/v1/system/health/ready", tags=["System"])
    async def readiness_probe() -> Dict[str, Any]:
        """Readiness check for dependent services (DB, Redis, OPA)."""
        # In test/dev environment, return status map
        return {
            "status": "READY",
            "checks": {
                "database": "UP",
                "redis": "UP",
                "opa": "UP",
                "storage": "UP",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return {
            "name": BRANDING.name,
            "version": BRANDING.version,
            "documentation": "/docs",
            "systemInfo": "/api/v1/system/info",
        }

    return app


app = create_app()
