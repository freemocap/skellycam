import logging

from fastapi import FastAPI

from skellycam.api.app.lifespan import lifespan
from skellycam.api.app_factory import register_routes, customize_swagger_ui
from skellycam.api.middleware.add_middleware import add_middleware
from skellycam.api.middleware.cors import cors

logger = logging.getLogger(__name__)


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