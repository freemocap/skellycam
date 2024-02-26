import logging
import multiprocessing

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse

import skellycam
from skellycam.backend.api_server.http_router import http_router
from skellycam.backend.controller import get_or_create_controller, Controller

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

        self._set_controller_exit_event(shutdown_event)

        self._register_routes()
        # self._register_middleware()
        self._customize_swagger_ui()
        self._timeout = timeout

        ready_event.set()

    def _set_controller_exit_event(self, shutdown_event: multiprocessing.Event):
        self.shutdown_event = shutdown_event
        controller: Controller = get_or_create_controller()
        # TODO - this is a weird work around, there is probably a better way to do this
        controller.set_exit_event(self.shutdown_event)

    def _register_routes(self):
        logger.info("Registering routes")

        @self.app.get("/")
        async def read_root():
            return RedirectResponse("/docs")

        self.app.include_router(http_router)

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
