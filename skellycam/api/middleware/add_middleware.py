import logging
import time
from fastapi import Request, Response

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def add_middleware(app: FastAPI):
    pass
    logger.debug("Adding middleware...")
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time
        # don't log /health requests
        if request.url.path == "/health":
            return response
        logger.debug(
            f"Request: {request.url} processed in {process_time:.6f} seconds and returned status code: {response.status_code}")
        return response
