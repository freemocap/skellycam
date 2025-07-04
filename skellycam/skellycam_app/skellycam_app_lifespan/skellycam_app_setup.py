import logging

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from starlette.responses import FileResponse

import skellycam
from skellycam.api.routers import SKELLYCAM_ROUTERS
from skellycam.system.default_paths import SKELLYCAM_FAVICON_ICO_PATH

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI):
    @app.get("/")
    async def read_root():
        return RedirectResponse("/docs")

    @app.get('/favicon.ico', include_in_schema=False)
    async def favicon():
        return FileResponse(SKELLYCAM_FAVICON_ICO_PATH)

    for router in SKELLYCAM_ROUTERS:
        for route in router.routes:
            logger.api(f"Registering routes: `/{skellycam.__package_name__}{route.path}`")
        app.include_router(router, prefix=f"/{skellycam.__package_name__}")


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
