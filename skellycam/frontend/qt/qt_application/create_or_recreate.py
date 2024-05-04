import logging

from skellycam.frontend.qt.qt_application.skellycam_qt_application import (
    SkellyCamQtApplication,
)

logger = logging.getLogger(__name__)

_QT_APPLICATION = None


def create_or_recreate_qt_application(
    hostname: str,
    port: int,
) -> "SkellyCamQtApplication":
    global _QT_APPLICATION

    try:

        def _delete_qt_application():
            if _QT_APPLICATION is not None:
                _QT_APPLICATION.quit()
                _QT_APPLICATION.deleteLater()

        def _create_qt_application():
            return SkellyCamQtApplication(
                hostname=hostname,
                port=port,
            )

        if _QT_APPLICATION is None:
            logger.info(f"Creating QApplication...")
            _QT_APPLICATION = _create_qt_application()

        else:
            logger.info(f"Recreating QApplication...")
            _delete_qt_application()
            _QT_APPLICATION = _create_qt_application()

        return _QT_APPLICATION
    except Exception as e:
        logger.error(f"Error occurred while creating or recreating QApplication: {e}")
        logger.exception(e)
        raise e