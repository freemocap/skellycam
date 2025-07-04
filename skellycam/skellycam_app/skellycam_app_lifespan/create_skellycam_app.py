import logging

from fastapi import FastAPI

from skellycam.api.middleware.add_middleware import add_middleware
from skellycam.api.middleware.cors import cors
from skellycam.skellycam_app.skellycam_app_lifespan.skellycam_app_lifespan import lifespan
from skellycam.skellycam_app.skellycam_app_lifespan.skellycam_app_setup import register_routes, customize_swagger_ui

logger = logging.getLogger(__name__)


def create_skellycam_fastapi_app() -> FastAPI:
    logger.api("Creating FastAPI app")
    app = FastAPI(lifespan=lifespan)
    cors(app)
    register_routes(app)
    add_middleware(app)
    customize_swagger_ui(app)
    return app
