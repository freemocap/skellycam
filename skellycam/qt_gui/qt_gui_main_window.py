import logging
import multiprocessing
from pathlib import Path
from typing import Union

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDockWidget, QMainWindow, QVBoxLayout, QWidget

from skellycam.qt_gui.css.qt_css_stylesheet import QT_CSS_STYLE_SHEET_STRING
from skellycam.qt_gui.widgets.qt_camera_config_parameter_tree_widget import (
    QtCameraConfigParameterTreeWidget,
)
from skellycam.qt_gui.widgets.qt_camera_controller_widget import (
    QtCameraControllerWidget,
)
from skellycam.qt_gui.widgets.qt_directory_view_widget import QtDirectoryViewWidget
from skellycam.qt_gui.widgets.qt_multi_camera_viewer_widget import (
    QtMultiCameraViewerWidget,
)
from skellycam.qt_gui.widgets.welcome_to_skellycam_widget import (
    WelcomeToSkellyCamWidget,
)

logger = logging.getLogger(__name__)

class QtGUIMainWindow(QMainWindow):

    def __init__(self, session_folder_path: Union[str, Path], parent=None):
        logger.info("Initializing QtGUIMainWindow")
        super().__init__()
        self.setGeometry(100, 100, 1600, 900)

        self._session_folder_path = session_folder_path

        self.setStyleSheet(QT_CSS_STYLE_SHEET_STRING)

        self.setWindowTitle("Skelly Cam \U0001F480 \U0001F4F8")
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._layout = QVBoxLayout()
        self._central_widget.setLayout(self._layout)

        self._welcome_to_skellycam_widget = WelcomeToSkellyCamWidget()
        self._layout.addWidget(self._welcome_to_skellycam_widget)

        self._qt_multi_camera_viewer_widget = QtMultiCameraViewerWidget(
            session_folder_path=self._session_folder_path, parent=self
        )
        self._qt_multi_camera_viewer_widget.resize(1280, 720)
        self._layout.addWidget(self._qt_multi_camera_viewer_widget)

        self._qt_camera_controller_dock_widget = QDockWidget("Camera Controller", self)
        self._qt_camera_controller_widget = QtCameraControllerWidget(
            qt_multi_camera_viewer_widget=self._qt_multi_camera_viewer_widget,
            parent=self,
        )
        self._qt_camera_controller_dock_widget.setWidget(
            self._qt_camera_controller_widget
        )
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea,
            self._qt_camera_controller_dock_widget,
        )

        self._parameter_tree_dock_widget = QDockWidget("Camera Settings", self)
        self._parameter_tree_dock_widget.setFloating(False)
        self._qt_camera_config_parameter_tree_widget = (
            QtCameraConfigParameterTreeWidget()
        )

        # self._layout.addWidget(self._qt_camera_config_parameter_tree_widget)
        self._parameter_tree_dock_widget.setWidget(
            self._qt_camera_config_parameter_tree_widget
        )
        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self._parameter_tree_dock_widget
        )

        self._directory_view_dock_widget = QDockWidget("Directory View", self)
        self._qt_directory_view_widget = QtDirectoryViewWidget(
            folder_path=self._session_folder_path
        )
        self._directory_view_dock_widget.setWidget(self._qt_directory_view_widget)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._directory_view_dock_widget
        )

        self._connect_signals_to_slots()

    def _connect_signals_to_slots(self):
        self._qt_multi_camera_viewer_widget.camera_group_created_signal.connect(
            self._qt_camera_config_parameter_tree_widget.update_camera_config_parameter_tree
        )

        self._qt_multi_camera_viewer_widget.camera_group_created_signal.connect(
            self._welcome_to_skellycam_widget.hide
        )

        self._qt_camera_config_parameter_tree_widget.emitting_camera_configs_signal.connect(
            self._qt_multi_camera_viewer_widget.incoming_camera_configs_signal
        )

    def closeEvent(self, a0) -> None:
        try:
            self._qt_multi_camera_viewer_widget.close()
        except Exception as e:
            logger.error(f"Error while closing the viewer widget: {e}")
        super().closeEvent(a0)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    main_window = QtGUIMainWindow()
    main_window.show()
    app.exec()
    for process in multiprocessing.active_children():
        logger.info(f"Terminating process: {process}")
        process.terminate()
    sys.exit()
