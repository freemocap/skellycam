import logging

from fastapi import FastAPI, APIRouter
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from fastapi.routing import APIWebSocketRoute, APIRoute

import skellycam
from skellycam.api.routes.http import enabled_routers
from skellycam.api.middleware.cors import cors

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


def create_app(*args, **kwargs) -> FastAPI:
    logger.api("Creating FastAPI app")
    app = FastAPI()
    cors(app)
    register_routes(app)
    customize_swagger_ui(app)
    return app
