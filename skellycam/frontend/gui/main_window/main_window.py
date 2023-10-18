import multiprocessing
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QDockWidget, QLabel

from skellycam import logger
from skellycam.backend.controller.commands.requests_commands import BaseInteraction, BaseResponse
from skellycam.frontend.gui.css.qt_css_stylesheet import QT_CSS_STYLE_SHEET_STRING
from skellycam.frontend.gui.main_window.helpers.child_widget_manager import ChildWidgetManager
from skellycam.frontend.gui.main_window.helpers.keyboard_shortcuts import KeyboardShortcuts
from skellycam.frontend.gui.widgets.camera_control_panel import CameraControlPanel
from skellycam.frontend.gui.widgets.cameras.camera_grid import (
    CameraGridView,
)
from skellycam.frontend.gui.widgets.config_parameter_tree import (
    CameraParameterTree,
)
from skellycam.frontend.gui.widgets.record_buttons_view import (
    RecordButtonsView,
)
from skellycam.frontend.gui.widgets.directory_view import DirectoryView
from skellycam.frontend.gui.widgets.welcome_view import (
    WelcomeView,
)
from skellycam.system.environment.default_paths import get_default_skellycam_base_folder_path, \
    PATH_TO_SKELLY_CAM_LOGO_PNG


class MainWindow(QMainWindow):
    interact_with_backend = Signal(BaseInteraction)

    def __init__(self,
                 exit_event: multiprocessing.Event,
                 reboot_event: multiprocessing.Event):
        logger.info("Initializing QtGUIMainWindow")
        super().__init__()

        self.shortcuts = KeyboardShortcuts(exit_event=exit_event,
                                           reboot_event=reboot_event)
        self.shortcuts.connect_shortcuts(self)
        self._initUI()
        self._child_widget_manager = ChildWidgetManager(main_window=self)

    def handle_backend_response(self, response: BaseResponse) -> None:
        self._child_widget_manager.handle_backend_response(response=response)

    def _initUI(self):
        self.setGeometry(100, 100, 1600, 900)
        if not Path(PATH_TO_SKELLY_CAM_LOGO_PNG).is_file():
            raise FileNotFoundError(f"Could not find logo at {PATH_TO_SKELLY_CAM_LOGO_PNG}")
        self.setWindowIcon(QIcon(PATH_TO_SKELLY_CAM_LOGO_PNG))
        self.setStyleSheet(QT_CSS_STYLE_SHEET_STRING)
        self.setWindowTitle("Skelly Cam \U0001F480 \U0001F4F8")

        self._layout = QVBoxLayout()
        self._create_central_widget()
        self._create_main_view()
        self._create_dock_tabs()

    def _create_central_widget(self):
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._central_widget.setLayout(self._layout)



    def _create_main_view(self):
        self.welcome_view = WelcomeView(parent=self)
        self._layout.addWidget(self.welcome_view)
        self.camera_grid_view = CameraGridView(parent=self)
        self.camera_grid_view.resize(1280, 720)
        self.record_buttons_view = RecordButtonsView(parent=self, )
        self._layout.addWidget(self.record_buttons_view)
        self._layout.addWidget(self.camera_grid_view)
        self.camera_grid_view.hide()
        self.record_buttons_view.hide()

    def _create_dock_tabs(self):
        self._create_camera_settings_dock()
        self._create_directory_dock()
        self.tabifyDockWidget(
            self.directory_view_dock,
            self.camera_settings_dock,
        )
        self.camera_settings_dock.raise_()


    def _create_directory_dock(self):
        self.directory_view_dock = QDockWidget("Directory View", self)
        self.directory_view = DirectoryView(folder_path=get_default_skellycam_base_folder_path())
        self.directory_view_dock.setWidget(self.directory_view)
        self.directory_view_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable,
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.directory_view_dock)
        self.directory_view_dock.hide()

    def _create_camera_settings_dock(self):
        self.camera_settings_dock = QDockWidget("Camera Settings", self)
        self.camera_settings_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable,
        )
        camera_settings_layout = QVBoxLayout()
        self.camera_control_panel = CameraControlPanel(parent=self)
        camera_settings_layout.addWidget(self.camera_control_panel)
        self.camera_parameter_tree = CameraParameterTree(parent=self)
        camera_settings_layout.addWidget(self.camera_parameter_tree)
        camera_settings_widget = QWidget(parent=self)
        camera_settings_widget.setLayout(camera_settings_layout)
        self.camera_settings_dock.setWidget(camera_settings_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.camera_settings_dock)
        self.camera_settings_dock.hide()

    def closeEvent(self, event):
        logger.info("Closing MainWindow...")
        self.shortcuts.quit()
        event.accept()
