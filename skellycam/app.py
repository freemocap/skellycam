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
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.system.default_paths import (
    SKELLYCAM_FAVICON_ICO_PATH,
    get_default_skellycam_base_folder_path,
)
from skellycam.system.telemetry.telemetry import initialize_telemetry, shutdown_telemetry
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
    # TODO - JSM NOTE - this was added to fix a mysterious bug that was popping up in my dev environment. I'm not sure if its necessary or even helpful. I think it creates a huge burst of python.exe's to be get spawned for a second or two on app start. We should revisit.
    ensure_bytecode_compiled()

    base_path = Path(get_default_skellycam_base_folder_path())
    base_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Base folder: {base_path}")

    # Initialize anonymous telemetry (respects user opt-out preference)
    initialize_telemetry()

    logger.success(
        f"SkellyCam API v{skellycam.__version__} started successfully 💀📸✨\n"
        f"Swagger API docs: {APP_URL}/docs"
    )

    yield

    # ===== SHUTDOWN =====
    logger.api("SkellyCam API shutting down...")

    shutdown_telemetry()

    # Just set the flag — __main__ owns the WorkerRegistry and calls shutdown_all()
    app.state.global_kill_flag.value = True

    logger.success("SkellyCam API shutdown complete - Goodbye! 👋")


def create_fastapi_app(
        *,
        global_kill_flag: multiprocessing.Value,
        worker_registry: WorkerRegistry,
) -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(lifespan=app_lifespan)

    app.state.global_kill_flag = global_kill_flag
    app.state.worker_registry = worker_registry

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

    for router in SKELLYCAM_ROUTERS:
        app.include_router(router)
        for route in router.routes:
            logger.api(f"Registered: {route.path}")


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
