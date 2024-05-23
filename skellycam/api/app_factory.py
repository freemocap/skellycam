import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, APIRouter
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from fastapi.routing import APIWebSocketRoute, APIRoute

import skellycam
from skellycam.__main__ import APP_URL
from skellycam.api.routes.http import enabled_routers
from skellycam.api.middleware.cors import cors
from skellycam.system.default_paths import get_default_skellycam_base_folder_path

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI):
    @app.get("/")
    async def read_root():
        return RedirectResponse("/docs")

    for name, router in enabled_routers.items():
        log_routes(name, router)
        app.include_router(router)


def log_routes(name, router: APIRouter):
    routes_str = ""
    for route in router.routes:
        if isinstance(route, APIRoute):
            description_str = str(route.description).splitlines()[0] if route.description else ""
            description_str = description_str.split(".")[0] if description_str else ""
            routes_str += f"\n\t{list(route.methods)} {route.path} {description_str}"
        elif isinstance(route, APIWebSocketRoute):
            routes_str += f"\n\t[WEBSOCKET] {route.path}"
    if len(router.on_startup) > 0:
        routes_str += "\n\t[ON STARTUP]:"
        for startup_handler in router.on_startup:
            routes_str += f"\n\t\t{startup_handler.__name__}"

    if len(router.on_shutdown) > 0:
        routes_str += "\n\t[ON SHUTDOWN]:"
        for shutdown_handler in router.on_shutdown:
            routes_str += f"\n\t\t{shutdown_handler.__name__}"

    logger.debug(f"Registering `{name}` router:{routes_str}")


def customize_swagger_ui(app: FastAPI):
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title="Welcome to the SkellyCam API 💀📸✨",
            version=skellycam.__version__,
            description=f"The FastAPI/Uvicorn/Swagger Backend UI for SkellyCam: {skellycam.__description__}",
            routes=app.routes,
        )
        # TODO - add SkellyCam logo?

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi


@asynccontextmanager
async def lifespan(app:FastAPI):
    logger.api("Skellycam API starting...")
    logger.info(f"Skellycam API base folder path: {get_default_skellycam_base_folder_path()}")
    Path(get_default_skellycam_base_folder_path()).mkdir(parents=True, exist_ok=True)
    logger.success(f"Skellycam API started successfully 💀📸✨")
    logger.api(f"Skellycam API  running on: {APP_URL} 👈[click to open backend UI in your browser]\n")
    yield
    logger.api("Skellycam API ending...")


def create_app(*args, **kwargs) -> FastAPI:
    logger.api("Creating FastAPI app")
    app = FastAPI(lifespan=lifespan)
    cors(app)
    register_routes(app)
    customize_swagger_ui(app)
    return app
