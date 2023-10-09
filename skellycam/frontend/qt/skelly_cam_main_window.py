import logging

from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QDockWidget

from skellycam.frontend.qt.css.qt_css_stylesheet import QT_CSS_STYLE_SHEET_STRING
from skellycam.frontend.qt.skelly_cam_widget import (
    SkellyCamWidget,
)
from skellycam.frontend.qt.widgets.skelly_cam_config_parameter_tree_widget import (
    SkellyCamParameterTreeWidget,
)
from skellycam.frontend.qt.widgets.skelly_cam_controller_widget import (
    SkellyCamControllerWidget,
)
from skellycam.frontend.qt.widgets.skelly_cam_directory_view_widget import SkellyCamDirectoryViewWidget
from skellycam.frontend.qt.widgets.welcome_to_skellycam_widget import (
    WelcomeToSkellyCamWidget,
)
from skellycam.system.environment.default_paths import get_default_skellycam_base_folder_path, \
    PATH_TO_SKELLY_CAM_LOGO_SVG

logger = logging.getLogger(__name__)


class SkellyCamMainWindow(QMainWindow):

    def __init__(self):
        logger.info("Initializing QtGUIMainWindow")
        super().__init__()
        self.setGeometry(100, 100, 1600, 900)
        self.setWindowIcon(QIcon(PATH_TO_SKELLY_CAM_LOGO_SVG))

        self.setStyleSheet(QT_CSS_STYLE_SHEET_STRING)

        self.setWindowTitle("Skelly Cam \U0001F480 \U0001F4F8")

        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._layout = QVBoxLayout()
        self._central_widget.setLayout(self._layout)

        self._welcome_to_skellycam_widget = WelcomeToSkellyCamWidget()
        self._layout.addWidget(self._welcome_to_skellycam_widget)

        self._camera_viewer_widget = SkellyCamWidget(parent=self)
        self._camera_viewer_widget.resize(1280, 720)

        self._qt_camera_controller_widget = SkellyCamControllerWidget(
            camera_viewer_widget=self._camera_viewer_widget,
            parent=self,
        )

        self._layout.addWidget(self._qt_camera_controller_widget)
        self._layout.addWidget(self._camera_viewer_widget)

        self._parameter_tree_dock_widget = QDockWidget("Camera Settings", self)
        self._parameter_tree_dock_widget.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable,
        )
        self._qt_camera_config_parameter_tree_widget = (
            SkellyCamParameterTreeWidget(self._camera_viewer_widget)
        )

        # self._layout.addWidget(self._qt_camera_config_parameter_tree_widget)
        self._parameter_tree_dock_widget.setWidget(
            self._qt_camera_config_parameter_tree_widget
        )
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._parameter_tree_dock_widget
        )

        self._directory_view_dock_widget = QDockWidget("Directory View", self)
        self._directory_view_widget = SkellyCamDirectoryViewWidget(
            folder_path=get_default_skellycam_base_folder_path(),
        )
        self._directory_view_dock_widget.setWidget(self._directory_view_widget)
        self._directory_view_dock_widget.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable,
        )
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._directory_view_dock_widget
        )

        self.tabifyDockWidget(
            self._directory_view_dock_widget,
            self._parameter_tree_dock_widget,
        )


    def closeEvent(self, a0) -> None:
        try:
            self._camera_viewer_widget.close()
        except Exception as e:
            logger.error(f"Error while closing the viewer widget: {e}")
        super().closeEvent(a0)
