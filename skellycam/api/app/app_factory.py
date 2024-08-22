import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from starlette.responses import FileResponse

import skellycam
from skellycam.api.app.app_state import get_app_state
from skellycam.api.app.lifespan import lifespan
from skellycam.api.middleware.cors import cors
from skellycam.api.routes.routers import enabled_routers
from skellycam.system.default_paths import FAVICON_PATH

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI):
    @app.get("/")
    async def read_root():
        return RedirectResponse("/docs")

    @app.get('/favicon.ico', include_in_schema=False)
    async def favicon():
        return FileResponse(FAVICON_PATH)

    for prefix, routers in enabled_routers.items():
        for name, router in routers.items():
            logger.api(f"Registering route: `{prefix}/{name}`")
            app.include_router(router, prefix=prefix)


def add_middleware(app: FastAPI):
    logger.debug("Adding middleware...")

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time
        logger.debug(
            f"Request: {request.url} processed in {process_time:.6f} seconds and returned status code: {response.status_code}")
        get_app_state().log_api_call(url_path=request.url.path,
                                     start_time=start_time,
                                     process_time=process_time,
                                     status_code=response.status_code)
        return response


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
    global FAST_API_APP
    logger.api("Creating FastAPI app")
    app = FastAPI(lifespan=lifespan)
    FAST_API_APP = app
    cors(app)
    register_routes(app)
    add_middleware(app)
    customize_swagger_ui(app)
    return app
