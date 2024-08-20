import logging

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse

import skellycam
from skellycam.api.lifespan import lifespan
from skellycam.api.middleware.cors import cors
from skellycam.api.routes.routers import enabled_routers

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI):
    @app.get("/")
    async def read_root():
        return RedirectResponse("/docs")

    for prefix, routers in enabled_routers.items():
        for name, router in routers.items():
            logger.api(f"Registering route: `{prefix}/{name}`")
            app.include_router(router, prefix=prefix)


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
    app = FastAPI(lifespan=lifespan)
    cors(app)
    register_routes(app)
    customize_swagger_ui(app)
    return app