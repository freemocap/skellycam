import logging
import multiprocessing

from PyQt6.QtWidgets import QWidget, QMainWindow, QVBoxLayout

from fast_camera_capture.controllers.qt_app.qt_camera_controller_widget import QtCameraControllerWidget
from fast_camera_capture.viewers.qt_app.qt_multi_camera_viewer_widget import QtMultiCameraViewerWidget

logger = logging.getLogger(__name__)

class ControllerMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._layout = QVBoxLayout()
        self._central_widget.setLayout(self._layout)

        self._camera_view_layout = QVBoxLayout()
        self._layout.addLayout(self._camera_view_layout)

        self._qt_multi_camera_viewer_widget = QtMultiCameraViewerWidget(parent=self)
        self._camera_view_layout.addWidget(self._qt_multi_camera_viewer_widget)

        self._qt_multi_camera_controller_widget = QtCameraControllerWidget(
            qt_multi_camera_viewer_widget=self._qt_multi_camera_viewer_widget,
            parent=self)

        self._camera_view_layout.addWidget(self._qt_multi_camera_controller_widget)

    def closeEvent(self, a0) -> None:
        try:
            self._qt_multi_camera_viewer_widget.close()
        except Exception as e:
            logger.error(f"Error while closing the viewer widget: {e}")
        super().closeEvent(a0)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    main_window = ControllerMainWindow()
    main_window.show()
    app.exec()
    for process in multiprocessing.active_children():
        logger.info(f"Terminating process: {process}")
        process.terminate()
    sys.exit()
