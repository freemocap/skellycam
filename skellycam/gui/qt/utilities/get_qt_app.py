from PySide6.QtWidgets import QApplication

QT_APP = None


def get_qt_app(sys_argv=None) -> QApplication:
    global QT_APP
    if QT_APP is None:
        QT_APP = QApplication(sys_argv)
    return QT_APP
