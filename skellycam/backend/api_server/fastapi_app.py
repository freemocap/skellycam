import logging
import multiprocessing
from datetime import datetime
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from fastapi.websockets import WebSocket

import skellycam
from skellycam.backend.api_server.backend_websocket import (
    BackendWebsocketManager,
)
from skellycam.backend.api_server.http_router import http_router

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
        # self._register_middleware()
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
            await ws_manager.receive_and_process_text_messages()

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

    # async def _register_middleware(self):
    #     @self.app.middleware("http")
    #     async def log_requests(
    #         request: Request, call_next: Callable[[Request], Response]
    #     ):
    #         request_id = id(request)
    #         start_time = datetime.now()
    #
    #         # Log the request start
    #         logging.info(
    #             f"Request {request_id}: {request.method} {request.url} - Start at {start_time}"
    #         )
    #
    #         # Process the request
    #         response = await call_next(request)
    #
    #         # Calculate request processing time
    #         process_time = (datetime.now() - start_time).total_seconds()
    #
    #         # Log the request end
    #         logging.info(
    #             f"Request {request_id}: {request.method} {request.url} - Completed in {process_time}s with status {response.status_code}"
    #         )
    #
    #         return response