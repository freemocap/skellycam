"""
Consolidated FastAPI app factory with proper lifecycle management.
"""
import logging
import multiprocessing
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from starlette.responses import FileResponse

import skellycam
from skellycam.api.http.app.health import health_router
from skellycam.api.http.app.shutdown import shutdown_router
from skellycam.api.middleware.add_middleware import add_middleware
from skellycam.api.middleware.cors import cors
from skellycam.api.routers import SKELLYCAM_ROUTERS
from skellycam.server.server_constants import APP_URL
from skellycam.skellycam_app.skellycam_app import create_skellycam_app
from skellycam.system.default_paths import (
    SKELLYCAM_FAVICON_ICO_PATH,
    get_default_skellycam_base_folder_path
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(
        app: FastAPI
) -> AsyncGenerator[None, None]:
    """
    Manage the application lifecycle.
    All startup and shutdown logic goes here.
    """
    # Startup
    logger.api("SkellyCam API starting...")

    # Ensure base folder exists
    base_path = Path(get_default_skellycam_base_folder_path())
    base_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Base folder: {base_path}")

    # Initialize the SkellyCam application
    skellycam_app = app.state.skellycam_app

    logger.success(
        f"SkellyCam API v{skellycam.__version__} started successfully 💀📸✨\n"
        f"Swagger API docs: {APP_URL}/docs"
    )

    # Let the app run
    yield

    # Shutdown
    logger.api("SkellyCam API shutting down...")

    # Cleanup SkellyCam application
    if hasattr(app.state, 'skellycam_app'):
        skellycam_app.shutdown()

    logger.success("SkellyCam API shutdown complete - Goodbye! 👋")


def create_fastapi_app(
        global_kill_flag: multiprocessing.Value
) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        global_kill_flag: Shared flag for coordinated shutdown

    Returns:
        Configured FastAPI application
    """
    # Create app with lifespan manager
    app = FastAPI(lifespan=app_lifespan)

    # Store dependencies in app state
    app.state.global_kill_flag = global_kill_flag
    app.state.skellycam_app = create_skellycam_app(
        global_kill_flag=global_kill_flag
    )

    # Configure CORS
    cors(app)

    # Register routes
    _register_routes(app)

    # Add middleware
    add_middleware(app)

    # Customize OpenAPI
    _customize_openapi(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register all application routes."""

    # Root redirect
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse("/docs")

    # Favicon
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(SKELLYCAM_FAVICON_ICO_PATH)

    # Health and shutdown routes (no prefix)
    for router in [health_router, shutdown_router]:
        app.include_router(router)
        for route in router.routes:
            logger.api(f"Registered: {route.path}")

    # Package routes (with prefix)
    prefix = f"/{skellycam.__package_name__}"
    for router in SKELLYCAM_ROUTERS:
        app.include_router(router, prefix=prefix)
        for route in router.routes:
            logger.api(f"Registered: {prefix}{route.path}")


def _customize_openapi(app: FastAPI) -> None:
    """Customize the OpenAPI schema."""

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title="SkellyCam API 💀📸✨",
            version=skellycam.__version__,
            description=(
                f"FastAPI Backend for SkellyCam: {skellycam.__description__}"
            ),
            routes=app.routes,
        )

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
