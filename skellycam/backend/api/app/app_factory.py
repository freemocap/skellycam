import logging

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse

import skellycam
from skellycam.backend.api.http import enabled_routers
from skellycam.backend.api.middleware.cors import cors

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI):
    @app.get("/")
    async def read_root():
        return RedirectResponse("/docs")

    for router in enabled_routers:
        app.include_router(router)


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
    logger.info("Creating FastAPI app")
    app = FastAPI()
    cors(app)
    register_routes(app)
    customize_swagger_ui(app)
    return app
