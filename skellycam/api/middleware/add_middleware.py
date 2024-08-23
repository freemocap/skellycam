import logging
import time

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response

from skellycam.api.app.app_state import get_app_state

logger = logging.getLogger(__name__)


def add_middleware(app: FastAPI):
    logger.debug("Adding middleware...")

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time
        logger.debug(
            f"Request: {request.url} processed in {process_time:.6f} seconds and returned status code: {response.status_code}")
        get_app_state().log_api_call(url_path=request.url.path,
                                     start_time=start_time,
                                     process_time=process_time,
                                     status_code=response.status_code)
        return response

    # @app.middleware("http")
    # async def send_app_state_update(request: Request, call_next):
    #     response: Response = await call_next(request)
    #     get_controller().ipc_queue.put(get_app_state().state_dto())
    #     return response
