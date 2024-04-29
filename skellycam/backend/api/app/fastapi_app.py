import logging

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse

import skellycam
from skellycam.backend.api.middleware.cors import cors
from skellycam.backend.api.routes import enabled_routers

logger = logging.getLogger(__name__)


class FastApiApp:
    def __init__(
        self,
    ):
        self.app = FastAPI()

        cors(self.app)

        self._register_routes()
        self._customize_swagger_ui()

    def _register_routes(self):
        @self.app.get("/")
        async def read_root():
            return RedirectResponse("/docs")

        for router in enabled_routers:
            self.app.include_router(router)

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

