import logging
import multiprocessing

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from fastapi.websockets import WebSocket

import skellycam
from skellycam.backend.api_server.backend_websocket import (
    BackendWebsocketManager,
)
from skellycam.backend.api_server.router import http_router

logger = logging.getLogger(__name__)


class FastApiApp:
    def __init__(
        self,
        ready_event: multiprocessing.Event,
        shutdown_event: multiprocessing.Event,
        timeout: float,
    ):
        logger.info("Creating FastAPI app")
        self.app = FastAPI()
        self._register_routes()
        self._customize_swagger_ui()
        self.shutdown_event = shutdown_event
        self._timeout = timeout
        ready_event.set()

    def _register_routes(self):
        logger.info("Registering routes")

        @self.app.get("/")
        async def read_root():
            return RedirectResponse("/docs")

        self.app.include_router(http_router)

        @self.app.websocket("/websocket")
        async def websocket_route(websocket: WebSocket):
            logger.info("WebSocket connection received")
            ws_manager = BackendWebsocketManager(
                websocket=websocket,
                shutdown_event=self.shutdown_event,
                timeout=self._timeout,
            )
            await ws_manager.accept_connection()
            await ws_manager.receive_and_process_messages()

            logger.info("WebSocket connection closed, shutting down...")
            self.shutdown_event.set()

    def _customize_swagger_ui(self):
        logger.info(f"Customizing Swagger UI at `/docs` endpoint")

        def custom_openapi():
            if self.app.openapi_schema:
                return self.app.openapi_schema
            openapi_schema = get_openapi(
                title="Welcome to the SkellyCam API 💀📸✨",
                version=skellycam.__version__,
                description=f"The FastAPI/Uvicorn/Swagger Backend UI for SkellyCam: {skellycam.__description__}",
                routes=self.app.routes,
            )
            # TODO - add SkellyCam logo?

            self.app.openapi_schema = openapi_schema
            return self.app.openapi_schema

        self.app.openapi = custom_openapi
