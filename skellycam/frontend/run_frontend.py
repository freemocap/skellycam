import logging
import multiprocessing
from multiprocessing import Process

logger = logging.getLogger(__name__)

from skellycam.frontend.application import create_or_recreate_qt_application


def run_qt_application(
    hostname: str,
    port: int,
    backend_timeout: float,
    reboot_event: multiprocessing.Event,
    shutdown_event: multiprocessing.Event,
):
    skellycam_qt_app = None
    try:
        skellycam_qt_app = create_or_recreate_qt_application(
            hostname=hostname,
            port=port,
            backend_timeout=backend_timeout,
            reboot_event=reboot_event,
            shutdown_event=shutdown_event,
        )
        ## TODO - Add some method to detect a "reboot" exit code and delete/recreate the qt app
        exit_code = skellycam_qt_app.exec()
    except Exception as e:
        logger.error(e)
        logger.exception(e)
        raise e
    finally:
        if skellycam_qt_app is not None:
            skellycam_qt_app.quit()
            skellycam_qt_app.deleteLater()
        shutdown_event.set()


def run_frontend(
    hostname: str,
    port: int,
    backend_timeout: float,
    reboot_event: multiprocessing.Event,
    shutdown_event: multiprocessing.Event,
) -> Process:
    logger.info(f"Starting frontend/client process...")
    frontend_process = Process(
        target=run_qt_application,
        args=(hostname,
              port,
              backend_timeout,
              reboot_event,
              shutdown_event),
    )
    frontend_process.start()
    if frontend_process.is_alive():
        logger.info(
            f"Frontend process started - client connected to backend server on: https://{hostname}:{port}"
        )
        return frontend_process
