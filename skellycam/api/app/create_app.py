import logging

from fastapi import FastAPI

from skellycam.api.app.app_setup import register_routes, customize_swagger_ui
from skellycam.api.app.lifespan import lifespan
from skellycam.api.middleware.add_middleware import add_middleware
from skellycam.api.middleware.cors import cors

logger = logging.getLogger(__name__)


def create_app(*args, **kwargs) -> FastAPI:
    logger.api("Creating FastAPI app")
    app = FastAPI(lifespan=lifespan)
    cors(app)
    register_routes(app)
    add_middleware(app)
    customize_swagger_ui(app)
    return app
