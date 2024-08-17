from PySide6.QtWidgets import QApplication

APP = None


def get_qt_app(sys_argv=None) -> QApplication:
    global APP
    if APP is None:
        APP = QApplication(sys_argv)
    return APP
