
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from skellycam.api.routers import camera_router
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import \
    detect_available_cameras


class FastAPIApp:
    def __init__(self):
        self.app = FastAPI()
        self._register_routes()
        self._customize_swagger_ui()

    def _register_routes(self):
        self.app.include_router(camera_router.router)
        self.app.get("/")(self.read_root)
        self.app.get("/detect/")(detect_available_cameras)

    async def read_root(self):
        return {"message": "Hello from SkellyCam 💀📸✨"}

    def _customize_swagger_ui(self):
        def custom_openapi():
            if self.app.openapi_schema:
                return self.app.openapi_schema
            openapi_schema = get_openapi(
                title="Welcome to the SkellyCam API 💀📸✨",
                version="insert version number here",
                description="wow cameras :O ",
                routes=self.app.routes,
            )
            # TODO - add SkellyCam logo?
            openapi_schema["info"]["x-logo"] = {
                "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
            }
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
