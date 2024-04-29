import logging
import multiprocessing

import uvicorn
from setproctitle import setproctitle

from skellycam.backend.api.app.fastapi import FastApiApp
from skellycam.backend.api.utilities.log_api_routes import log_api_routes

logger = logging.getLogger(__name__)


def create_app(*args, **kwargs):
    logger.info("Creating FastAPI app")
    _app = FastApiApp().app
    return _app

def run_uvicorn_server(
    hostname: str,
    port: int,
):
    setproctitle("backend_server")
    logger.info(
        f"Starting uvicorn server on with hostname: `{hostname}` on port: `{port}`"
    )
    try:
        log_api_routes(create_app(), hostname, port)

        uvicorn.run(
            "skellycam.backend.api.app.app_factory:create_app",
            host=hostname,
            port=port,
            log_level="debug",
            reload=True,
            factory=True
        )
    except Exception as e:
        logger.error(f"A fatal error occurred in the uvicorn server: {e}")
        logger.exception(e)
        raise e
    finally:
        logger.info(f"Shutting down uvicorn server")