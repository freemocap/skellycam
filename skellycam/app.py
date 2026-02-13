"""
Consolidated FastAPI app factory with proper lifecycle management.
"""
import logging
import multiprocessing
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import skellycam
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from skellycam.api.http.app.health import health_router
from skellycam.api.http.app.shutdown import shutdown_router
from skellycam.api.middleware.add_middleware import add_middleware
from skellycam.api.middleware.cors import cors
from skellycam.api.routers import SKELLYCAM_ROUTERS
from skellycam.api.server_constants import APP_URL
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry
from skellycam.system.default_paths import (
    SKELLYCAM_FAVICON_ICO_PATH,
    get_default_skellycam_base_folder_path,
)
from skellycam.utilities.ensure_compiled import ensure_bytecode_compiled
from starlette.responses import FileResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage the application lifecycle."""
    # ===== STARTUP =====
    logger.api("SkellyCam API starting...")

    # Pre-compile .py → .pyc so spawned child processes hit fast .pyc reads
    # instead of racing on .py file access (Windows multiprocessing.spawn issue)
    ensure_bytecode_compiled()

    base_path = Path(get_default_skellycam_base_folder_path())
    base_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Base folder: {base_path}")

    logger.success(
        f"SkellyCam API v{skellycam.__version__} started successfully 💀📸✨\n"
        f"Swagger API docs: {APP_URL}/docs"
    )

    yield

    # ===== SHUTDOWN =====
    logger.api("SkellyCam API shutting down...")

    # Just set the flag — __main__ owns the ProcessRegistry and calls shutdown_all()
    app.state.global_kill_flag.value = True

    logger.success("SkellyCam API shutdown complete - Goodbye! 👋")


def create_fastapi_app(
        *,
        global_kill_flag: multiprocessing.Value,
        process_registry: ProcessRegistry,
) -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(lifespan=app_lifespan)

    app.state.global_kill_flag = global_kill_flag
    app.state.process_registry = process_registry

    cors(app)
    _register_routes(app)
    add_middleware(app)
    _customize_openapi(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register all application routes."""

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse("/docs")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(SKELLYCAM_FAVICON_ICO_PATH)

    for router in [health_router, shutdown_router]:
        app.include_router(router)
        for route in router.routes:
            logger.api(f"Registered: {route.path}")

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
