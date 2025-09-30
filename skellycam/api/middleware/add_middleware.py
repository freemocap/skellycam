import logging
import time
import json
from fastapi import Request, Response, FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def add_middleware(app: FastAPI) -> None:
    logger.debug("Adding middleware...")

    @app.middleware("http")
    async def log_requests(request: Request, call_next) -> Response:
        start_time = time.time()

        try:
            response: Response = await call_next(request)
            process_time = time.time() - start_time

            # Don't log /health requests
            if request.url.path == "/health":
                return response

            # Log successful requests
            if response.status_code < 400:
                logger.debug(
                    f"Request: {request.url} processed in {process_time:.6f} seconds "
                    f"and returned status code: {response.status_code}"
                )
            else:
                # Log failed requests with more details
                logger.error(
                    f"Failed request: {request.method} {request.url}\n"
                    f"  Status: {response.status_code}\n"
                    f"  Process time: {process_time:.6f}s"
                )

            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Exception during request: {request.method} {request.url}\n"
                f"  Error: {type(e).__name__}: {str(e)}\n"
                f"  Process time: {process_time:.6f}s",
                exc_info=True
            )
            raise

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
            request: Request,
            exc: RequestValidationError
    ) -> Response:
        """Handle validation errors (422) and log details"""
        from fastapi.responses import JSONResponse

        # Try to get the request body for logging
        try:
            body = await request.body()
            body_str = body.decode('utf-8') if body else "empty"
        except Exception:
            body_str = "unable to read"

        logger.error(
            f"Validation error (422): {request.method} {request.url}\n"
            f"  Errors: {json.dumps(exc.errors(), indent=2)}\n"
            f"  Request body: {body_str}",
            exc_info=True
        )

        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "body": exc.body}
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
            request: Request,
            exc: StarletteHTTPException
    ) -> Response:
        """Handle HTTP exceptions and log details"""
        from fastapi.responses import JSONResponse

        logger.error(
            f"HTTP {exc.status_code} error: {request.method} {request.url}\n"
            f"  Detail: {exc.detail}",
            exc_info=True
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None)
        )