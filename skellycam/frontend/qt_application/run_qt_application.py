import logging
import multiprocessing

from setproctitle import setproctitle

from skellycam.frontend.qt_application import create_or_recreate_qt_application

logger = logging.getLogger(__name__)


def run_qt_application(
    hostname: str,
    port: int,
):
    setproctitle("gui_process")
    skellycam_qt_app = None
    try:
        skellycam_qt_app = create_or_recreate_qt_application(
            hostname=hostname,
            port=port,
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
