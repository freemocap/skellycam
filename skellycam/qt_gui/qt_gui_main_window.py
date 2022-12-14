import logging
import multiprocessing
from pathlib import Path
from typing import Union

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDockWidget, QMainWindow, QVBoxLayout, QWidget

from skellycam.qt_gui.css.qt_css_stylesheet import QT_CSS_STYLE_SHEET_STRING
from skellycam.qt_gui.widgets.skelly_cam_config_parameter_tree_widget import (
    SkellyCamParameterTreeWidget,
)
from skellycam.qt_gui.widgets.skelly_cam_controller_widget import (
    SkellyCamControllerWidget,
)
from skellycam.qt_gui.widgets.skelly_cam_directory_view_widget import SkellyCamDirectoryViewWidget
from skellycam.qt_gui.widgets.skelly_cam_viewer_widget import (
    SkellyCamViewerWidget,
)
from skellycam.qt_gui.widgets.welcome_to_skellycam_widget import (
    WelcomeToSkellyCamWidget,
)
from skellycam.system.environment.default_paths import get_default_session_folder_path, \
    get_default_skellycam_base_folder_path

logger = logging.getLogger(__name__)


class QtGUIMainWindow(QMainWindow):

    def __init__(self,
                 session_folder_path: Union[str, Path] = None,
                 parent=None):
        logger.info("Initializing QtGUIMainWindow")
        super().__init__(parent=parent)
        self.setGeometry(100, 100, 1600, 900)

        if session_folder_path is None:
            self._session_folder_path = get_default_session_folder_path()
        else:
            self._session_folder_path = session_folder_path

        self._base_folder_path =  get_default_skellycam_base_folder_path()

        self.setStyleSheet(QT_CSS_STYLE_SHEET_STRING)

        self.setWindowTitle("Skelly Cam \U0001F480 \U0001F4F8")
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._layout = QVBoxLayout()
        self._central_widget.setLayout(self._layout)

        self._welcome_to_skellycam_widget = WelcomeToSkellyCamWidget()
        self._layout.addWidget(self._welcome_to_skellycam_widget)

        self._camera_viewer_widget = SkellyCamViewerWidget(
            session_folder_path=self._session_folder_path, parent=self
        )
        self._camera_viewer_widget.resize(1280, 720)

        self._qt_camera_controller_widget = SkellyCamControllerWidget(
            camera_viewer_widget=self._camera_viewer_widget,
            parent=self,
        )

        self._layout.addWidget(self._qt_camera_controller_widget)
        self._layout.addWidget(self._camera_viewer_widget)

        self._parameter_tree_dock_widget = QDockWidget("Camera Settings", self)


        self._qt_camera_config_parameter_tree_widget = (
            SkellyCamParameterTreeWidget(self._camera_viewer_widget)
        )

        # self._layout.addWidget(self._qt_camera_config_parameter_tree_widget)
        self._parameter_tree_dock_widget.setWidget(
            self._qt_camera_config_parameter_tree_widget
        )
        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self._parameter_tree_dock_widget
        )

        self._directory_view_dock_widget = QDockWidget("Directory View", self)
        self._directory_view_widget = SkellyCamDirectoryViewWidget(
            folder_path=self._base_folder_path
        )
        self._directory_view_dock_widget.setWidget(self._directory_view_widget)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._directory_view_dock_widget
        )

        self._connect_signals_to_slots()

    def _connect_signals_to_slots(self):
        self._camera_viewer_widget.camera_group_created_signal.connect(
            self._qt_camera_config_parameter_tree_widget.update_camera_config_parameter_tree
        )

        self._camera_viewer_widget.detect_available_cameras_push_button.clicked.connect(
            self._welcome_to_skellycam_widget.hide
        )

        self._qt_camera_config_parameter_tree_widget.emitting_camera_configs_signal.connect(
            self._camera_viewer_widget.incoming_camera_configs_signal
        )

        self._camera_viewer_widget.new_recording_video_folder_created_signal.connect(
            self._directory_view_widget.expand_directory_to_path
        )

    def closeEvent(self, a0) -> None:

        remove_empty_directories(get_default_skellycam_base_folder_path())

        try:
            self._camera_viewer_widget.close()
        except Exception as e:
            logger.error(f"Error while closing the viewer widget: {e}")
        super().closeEvent(a0)

def remove_empty_directories(root_dir: Union[str, Path]):
    """
    Recursively remove empty directories from the root directory
    :param root_dir: The root directory to start removing empty directories from
    """
    for path in Path(root_dir).rglob("*"):
        if path.is_dir() and not any(path.iterdir()):
            logger.info(f"Removing empty directory: {path}")
            path.rmdir()
        elif path.is_dir() and any(path.iterdir()):
            remove_empty_directories(path)
        else:
            continue

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
