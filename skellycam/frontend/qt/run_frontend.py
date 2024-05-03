import logging
from multiprocessing import Process

from skellycam.frontend.qt.qt_application.run_qt_application import run_qt_application

logger = logging.getLogger(__name__)


def run_frontend(
    hostname: str,
    port: int,
) -> Process:
    logger.info(f"Starting frontend process...")
    frontend_process = Process(
        target=run_qt_application,
        args=(hostname, port),
    )
    frontend_process.start()
    if frontend_process.is_alive():
        logger.info(
            f"Frontend process started - client connected to backend server with hostname: `{hostname}` on port: `{port}`"
        )
        return frontend_process
