import multiprocessing
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QDockWidget

from skellycam import logger
from skellycam.data_models.request_response_update import UpdateModel, BaseMessage, EventTypes
from skellycam.frontend.gui.css.qt_css_stylesheet import QT_CSS_STYLE_SHEET_STRING
from skellycam.frontend.gui.main_window.helpers.keyboard_shortcuts import KeyboardShortcuts
from skellycam.frontend.gui.main_window.helpers.view_updater import ViewUpdater
from skellycam.frontend.gui.widgets.cameras.camera_grid import (
    CameraGridView,
)
from skellycam.frontend.gui.widgets.config_parameter_tree import (
    CameraSettingsView,
)
from skellycam.frontend.gui.widgets.control_panel import (
    RecordButtonsView,
)
from skellycam.frontend.gui.widgets.directory_view import DirectoryView
from skellycam.frontend.gui.widgets.welcome_view import (
    WelcomeView,
)
from skellycam.system.environment.default_paths import get_default_skellycam_base_folder_path, \
    PATH_TO_SKELLY_CAM_LOGO_PNG


class ChildWidgetManager:
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window

    def handle_message(self, message: BaseMessage):
        if message.event == EventTypes.SESSION_STARTED:
            message.data["camera_configs"]= self.main_window.camera_settings_view.get_camera_configs()


class MainWindow(QMainWindow):
    updated = Signal(UpdateModel)

    def __init__(self, exit_event: multiprocessing.Event, reboot_event: multiprocessing.Event):
        logger.info("Initializing QtGUIMainWindow")
        super().__init__()

        self.shortcuts = KeyboardShortcuts(exit_event=exit_event,
                                           reboot_event=reboot_event)
        self.shortcuts.connect_shortcuts(self)
        self._initUI()
        self._view_updater = ViewUpdater(main_window=self)
        self._child_widget_manager = ChildWidgetManager(main_window=self)

    def emit_update(self, update: UpdateModel) -> None:
        logger.trace(f"Emitting update signal with data: {update} from MainWindow")
        self.updated.emit(update)
        self.update_view(update)

    def update_view(self, message: BaseMessage) -> None:
        self._view_updater.handle_message(message)

    def _create_central_widget(self):
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._central_widget.setLayout(self._layout)

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

    def _create_main_view(self):
        self.welcome_view = WelcomeView(parent=self)
        self._layout.addWidget(self.welcome_view)
        self.camera_grid_view = CameraGridView(parent=self)
        self.camera_grid_view.resize(1280, 720)
        self.record_buttons_view = RecordButtonsView(
            camera_grid=self.camera_grid_view,
            parent=self,
        )
        self._layout.addWidget(self.record_buttons_view)
        self._layout.addWidget(self.camera_grid_view)
        self.camera_grid_view.hide()
        self.record_buttons_view.hide()

    def _create_dock_tabs(self):
        self._create_parameter_tree_dock()
        self._create_directory_dock()
        self.tabifyDockWidget(
            self._directory_view_dock,
            self._camera_settings_view_dock,
        )

    def _create_directory_dock(self):
        self._directory_view_dock = QDockWidget("Directory View", self)
        self.directory_view = DirectoryView(
            folder_path=get_default_skellycam_base_folder_path(),
        )
        self._directory_view_dock.setWidget(self.directory_view)
        self._directory_view_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable,
        )
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._directory_view_dock
        )

    def _create_parameter_tree_dock(self):
        self._camera_settings_view_dock = QDockWidget("Camera Settings", self)
        self._camera_settings_view_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable,
        )
        self.camera_settings_view = (
            CameraSettingsView(self.camera_grid_view)
        )
        # self._layout.addWidget(self._qt_camera_config_parameter_tree_widget)
        self._camera_settings_view_dock.setWidget(
            self.camera_settings_view
        )
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._camera_settings_view_dock
        )
