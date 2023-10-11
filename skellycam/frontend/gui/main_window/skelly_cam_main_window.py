import multiprocessing

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QDockWidget

from skellycam import logger
from skellycam.data_models.request_response import UpdateModel
from skellycam.frontend.gui.css.qt_css_stylesheet import QT_CSS_STYLE_SHEET_STRING
from skellycam.frontend.gui.main_window.keyboard_shortcuts import KeyboardShortcuts
from skellycam.frontend.gui.widgets.cameras.camera_grid import (
    CameraGrid,
)
from skellycam.frontend.gui.widgets.config_parameter_tree import (
    SkellyCamParameterTreeWidget,
)
from skellycam.frontend.gui.widgets.control_panel import (
    ControlPanel,
)
from skellycam.frontend.gui.widgets.directory_view import SkellyCamDirectoryViewWidget
from skellycam.frontend.gui.widgets.welcome import (
    Welcome,
)
from skellycam.system.environment.default_paths import get_default_skellycam_base_folder_path, \
    PATH_TO_SKELLY_CAM_LOGO_SVG


class MainWindow(QMainWindow):
    updated = Signal(UpdateModel)

    def __init__(self, exit_event: multiprocessing.Event, reboot_event: multiprocessing.Event):
        logger.info("Initializing QtGUIMainWindow")
        super().__init__()
        self._layout = QVBoxLayout()
        self._create_central_widget()

        self.shortcuts = KeyboardShortcuts(exit_event=exit_event,
                                           reboot_event=reboot_event)
        self.shortcuts.connect_shortcuts(self)
        self._initUI()

    def emit_update(self, update: UpdateModel) -> None:
        logger.trace(f"Emitting update signal with data: {update} from MainWindow")
        self.updated.emit(update)

    def _create_central_widget(self):
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._central_widget.setLayout(self._layout)

    def _initUI(self):
        self.setGeometry(100, 100, 1600, 900)
        self.setWindowIcon(QIcon(PATH_TO_SKELLY_CAM_LOGO_SVG))
        self.setStyleSheet(QT_CSS_STYLE_SHEET_STRING)
        self.setWindowTitle("Skelly Cam \U0001F480 \U0001F4F8")

        self._welcome_widget = Welcome(parent=self)
        self._layout.addWidget(self._welcome_widget)

        self._camera_grid_widget = CameraGrid(parent=self)
        self._camera_grid_widget.resize(1280, 720)

        self._control_panel = ControlPanel(
            camera_viewer_widget=self._camera_grid_widget,
            parent=self,
        )
        self._layout.addWidget(self._control_panel)
        self._layout.addWidget(self._camera_grid_widget)

        self._create_dock_tabs()

    def _create_dock_tabs(self):
        self._create_parameter_tree_dock()
        self._create_directory_dock()
        self.tabifyDockWidget(
            self._directory_view_dock_widget,
            self._parameter_tree_dock,
        )

    def _create_directory_dock(self):
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

    def _create_parameter_tree_dock(self):
        self._parameter_tree_dock = QDockWidget("Camera Settings", self)
        self._parameter_tree_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable,
        )
        self._parameter_tree_widget = (
            SkellyCamParameterTreeWidget(self._camera_grid_widget)
        )
        # self._layout.addWidget(self._qt_camera_config_parameter_tree_widget)
        self._parameter_tree_dock.setWidget(
            self._parameter_tree_widget
        )
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._parameter_tree_dock
        )

    def closeEvent(self, a0) -> None:
        try:
            self._camera_grid_widget.close()
        except Exception as e:
            logger.error(f"Error while closing the viewer widget: {e}")
        super().closeEvent(a0)
