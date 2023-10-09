import logging

from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

APP = None
def get_or_create_qt_app(sys_argv=None) -> QApplication:
    global APP
    if APP is None:
        logger.info(f"Creating QApplication...")
        APP = QApplication(sys_argv)
    return APP
