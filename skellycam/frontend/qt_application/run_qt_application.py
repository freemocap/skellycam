import multiprocessing

from skellycam.frontend.qt_application import create_or_recreate_qt_application

import logging

logger = logging.getLogger(__name__)


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
