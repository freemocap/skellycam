import logging
import multiprocessing

import uvicorn

from skellycam.backend.api_server.fastapi_app import FastApiApp
from skellycam.backend.api_server.log_api_routes import log_api_routes

logger = logging.getLogger(__name__)


def run_uvicorn_server(
    hostname: str,
    port: int,
    ready_event: multiprocessing.Event,
    shutdown_event: multiprocessing.Event,
    timeout: float,
):
    logger.info(f"Starting uvicorn server on: https://{hostname}:{port}")
    try:
        app = FastApiApp(
            ready_event=ready_event, shutdown_event=shutdown_event, timeout=timeout
        ).app
        log_api_routes(app, hostname, port)
        uvicorn.run(
            app,
            host=hostname,
            port=port,
            log_level="debug"
            # reload=True
        )
    except Exception as e:
        logger.error(f"A fatal error occurred in the uvicorn server: {e}")
        logger.exception(e)
        raise e
    finally:
        logger.info(f"Shutting down uvicorn server")
        shutdown_event.set()
