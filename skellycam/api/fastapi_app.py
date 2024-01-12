
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from starlette.responses import RedirectResponse

import skellycam
from skellycam.api import router


class FastApiApp:
    def __init__(self):
        self.app = FastAPI()
        self._register_routes()
        self._customize_swagger_ui()

    def _register_routes(self):
        self.app.get("/")(self.read_root)
        self.app.include_router(router.router)

    async def read_root(self):
        # return {"message": "Hello from SkellyCam 💀📸✨"}
        return RedirectResponse("/docs")

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

        # TODO - ask the machine what this stuff below is and what it is good for
        # self.app.swagger_ui_init_oauth = {
        #     "clientId": "your-client-id",
        #     "clientSecret": "your-client-secret-if-required",
        #     "realm": "your-realms",
        #     "appName": "your-app-name",
        #     "scopeSeparator": " ",
        #     "additionalQueryStringParams": {"test": "Hello World"},
        # }
