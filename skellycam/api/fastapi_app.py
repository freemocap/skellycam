import multiprocessing

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from fastapi.websockets import WebSocket

import skellycam
from skellycam.api.router import http_router
from skellycam.backend.system.environment.get_logger import logger


class FastApiApp:
    def __init__(self, ready_event: multiprocessing.Event):
        self.app = FastAPI()
        self._register_routes()
        self._customize_swagger_ui()
        ready_event.set()

    def _register_routes(self):
        @self.app.get("/")
        async def read_root():
            return RedirectResponse("/docs")

        self.app.include_router(http_router)

        @self.app.websocket("/websocket")
        async def websocket_route(websocket: WebSocket):
            logger.info("WebSocket connection received")
            await websocket.accept()
            while True:
                data = await websocket.receive_bytes()
                logger.info(f"Data received: {data}")
                response_message = f"received bytes: {data}"
                await websocket.send_bytes(bytes(response_message, "utf-8"))
            # ws_manager = BackendWebSocketConnectionManager(websocket)
            # await ws_manager.accept_connection()
            # await ws_manager.receive_and_process_messages()

    def _customize_swagger_ui(self):
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
