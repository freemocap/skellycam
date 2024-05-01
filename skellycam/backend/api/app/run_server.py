import logging

import uvicorn

logger = logging.getLogger(__name__)

def run_uvicorn_server(
        hostname: str,
        port: int,
):

    try:
        uvicorn.run(
            "skellycam.backend.api.app.app_factory:create_app",
            host=hostname,
            port=port,
            log_level="info",
            reload=True,
            factory=True
        )
    except Exception as e:
        logger.error(f"A fatal error occurred in the uvicorn server: {e}")
        logger.exception(e)
        raise e
    finally:
        logger.info(f"Shutting down uvicorn server")
