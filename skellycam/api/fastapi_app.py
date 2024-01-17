from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from starlette.responses import RedirectResponse
from starlette.websockets import WebSocket

import skellycam
from skellycam.api.router import http_router
from skellycam.api.backend_websocket import backend_websocket_connection


class FastApiApp:
    def __init__(self):
        self.app = FastAPI()
        self._register_routes()
        self._customize_swagger_ui()

    def _register_routes(self):
        @self.app.get("/")
        async def read_root():
            return RedirectResponse("/docs")

        self.app.include_router(http_router)

        @self.app.websocket("/websocket")
        async def websocket_route(websocket: WebSocket):
            await backend_websocket_connection(websocket)

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
