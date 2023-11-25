from PySide6.QtWidgets import QApplication

from skellycam.system.environment.get_logger import logger

_QT_APPLICATION = None

def create_or_recreate_qt_application(sys_argv=None) -> QApplication:
    global _QT_APPLICATION
    if _QT_APPLICATION is None:
        logger.info(f"Creating QApplication...")
        _QT_APPLICATION = QApplication(sys_argv or [])
    else:
        logger.info(f"Recreating QApplication...")
        _QT_APPLICATION.deleteLater()
        _QT_APPLICATION = QApplication(sys_argv or [])
    return _QT_APPLICATION