import logging
import multiprocessing
import threading
import time
from pathlib import Path
from typing import Union

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDockWidget, QMainWindow, QVBoxLayout, QWidget, QCheckBox
from pydantic import BaseModel

from skellycam import CameraConfigs
from skellycam.core.recorders.start_recording_request import StartRecordingRequest
from skellycam.gui.qt.widgets.keyboard_shortcuts import KeyboardShortcuts
from skellycam.skellycam_app.skellycam_app_state import SkellycamAppStateDTO
from skellycam.gui.qt.client.gui_client import SkellycamFrontendClient
from skellycam.gui.qt.css.qt_css_stylesheet import QT_CSS_STYLE_SHEET_STRING
from skellycam.gui.qt.widgets.camera_widgets.camera_panel import SkellycamCameraPanel
from skellycam.gui.qt.widgets.connect_to_cameras_button import ConnectToCamerasButton
from skellycam.gui.qt.widgets.side_panel_widgets.app_state_viewer_widget import SkellycamAppStateJsonViewer
from skellycam.gui.qt.widgets.side_panel_widgets.camera_control_panel import (
    SkellycamCameraControlPanel,
)
from skellycam.gui.qt.widgets.side_panel_widgets.skellycam_directory_view import SkellyCamDirectoryViewWidget
from skellycam.gui.qt.widgets.welcome_to_skellycam_widget import (
    WelcomeToSkellyCamWidget,
)
from skellycam.system.default_paths import get_default_skellycam_base_folder_path, \
    get_default_skellycam_recordings_path, SKELLYCAM_FAVICON_ICO_PATH
from skellycam.system.device_detection.detect_available_cameras import get_available_cameras, CameraDetectionStrategies

logger = logging.getLogger(__name__)

GUI_STATE_FILE_PATH = str(Path(__file__).parent/ "gui_state.json")
class GuiState(BaseModel):
    """
    Class to hold the state of the GUI
    """
    connect_automatically_checkbox: bool = False
    use_clientside_camera_detection: bool = True
    camera_configs: CameraConfigs| None = None

class SkellyCamMainWindow(QMainWindow):

    def __init__(self,
                 global_kill_flag: multiprocessing.Value,
                 parent=None):
        super().__init__(parent=parent)
        self._global_kill_flag = global_kill_flag
        # self._log_view_widget = LogViewWidget(global_kill_flag=global_kill_flag,
        #                                       parent=self)  # start this first so it will grab the setup logging
        self._client = SkellycamFrontendClient(self)
        self._client.connect_websocket()

        self._initUI()

        self._connect_signals_to_slots()

    def _initUI(self):
        self.setGeometry(100, 100, 1600, 900)
        self.setWindowIcon(QIcon(SKELLYCAM_FAVICON_ICO_PATH))
        self.setStyleSheet(QT_CSS_STYLE_SHEET_STRING)
        self.setWindowTitle("Skelly Cam \U0001F480 \U0001F4F8")
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._layout = QVBoxLayout()
        self._central_widget.setLayout(self._layout)


        self.keyboard_shortcuts = KeyboardShortcuts(self)

        # Welcome View
        self._welcome_to_skellycam_widget = WelcomeToSkellyCamWidget()
        self._layout.addWidget(self._welcome_to_skellycam_widget)
        self._welcome_connect_to_cameras_button = ConnectToCamerasButton(parent=self)
        self._layout.addWidget(self._welcome_connect_to_cameras_button)


        # Camera Panel
        self._skellycam_camera_panel = SkellycamCameraPanel(parent=self)
        self._skellycam_camera_panel.hide()
        self._layout.addWidget(self._skellycam_camera_panel)

        self._control_panel_dock = QDockWidget("Camera Settings", self)
        self._control_panel_dock.resize(300, self._control_panel_dock.height())
        self._control_panel_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable,
        )

        # Side Panel
        # Camera Settings Panel
        self._control_panel = (
            SkellycamCameraControlPanel(self._skellycam_camera_panel)
        )
        self._control_panel_dock.setWidget(
            self._control_panel
        )
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._control_panel_dock
        )

        # Directory View
        self._directory_view_dock = QDockWidget("Directory View", self)
        self._directory_view_widget = SkellyCamDirectoryViewWidget(
            folder_path=get_default_skellycam_recordings_path()
        )
        self._directory_view_dock.setWidget(self._directory_view_widget)
        self._directory_view_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable,
        )
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._directory_view_dock
        )
        self._backend_app_state_json_dock = QDockWidget("App State (JSON)", self)
        self._app_state_json_widget = SkellycamAppStateJsonViewer()
        self._backend_app_state_json_dock.setWidget(self._app_state_json_widget)
        self._backend_app_state_json_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable,
        )
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._backend_app_state_json_dock
        )
        self.tabifyDockWidget(
            self._backend_app_state_json_dock,
            self._directory_view_dock,
        )
        #
        # #Bottom Panel
        # log_view_dock_widget = QDockWidget("Log View", self)
        # self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_view_dock_widget)
        # log_view_dock_widget.setWidget(self._log_view_widget)
        # log_view_dock_widget.setFeatures(
        #     QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        # )

        self._load_gui_state()
        # if self._control_panel.connect_automatically_checkbox.isChecked():
        #     self.connect_to_cameras()


    def check_if_should_close(self):
        if self._global_kill_flag.value:
            logger.gui("Global kill flag is `True`, closing QT GUI")
            self.close()
            return

    def _connect_signals_to_slots(self):

        self._welcome_connect_to_cameras_button.button.clicked.connect(
            self._hide_welcome_view
        )

        self._welcome_connect_to_cameras_button.button.clicked.connect(self.connect_to_cameras)

        # self._control_panel.connect_cameras_button.clicked.connect(
        #     self._hide_welcome_view)

        self._control_panel.detect_available_cameras_button.clicked.connect(
            self._hide_welcome_view)

        # websocket
        self._client.websocket_client.new_frontend_payload_available.connect(
            self._skellycam_camera_panel.camera_view_grid.handle_new_frontend_payload
        )
        self._client.websocket_client.new_app_state_available.connect(
            self._handle_new_app_state
        )
        self._client.websocket_client.new_recording_info_available.connect(
            self._skellycam_camera_panel.recording_panel.handle_new_recording_info
        )
        self._client.websocket_client.new_recording_info_available.connect(
            self._directory_view_widget.handle_new_recording_info
        )

        # Camera Control Panel
        # self._control_panel.detect_available_cameras_button.clicked.connect(
        #     lambda: self._control_panel.camera_settings_panel.update_camera_configs(
        #         get_available_cameras(CameraDetectionStrategies.OPENCV)
        #     )
        # )
        # self._control_panel.connect_cameras_button.clicked.connect(
        #     lambda: self._client.apply_settings_to_cameras(self._control_panel.user_selected_camera_configs)
        # )
        self._control_panel.apply_settings_to_cameras_button.clicked.connect(
            lambda: self._client.cameras_connect_apply(self._control_panel.user_selected_camera_configs)
        )
        self._control_panel.close_cameras_button.clicked.connect(
            self.close_cameras
        )
        self._control_panel.close_cameras_button.clicked.connect(
            self._skellycam_camera_panel.camera_view_grid.clear_camera_views
        )

        # Recording Panel
        self._skellycam_camera_panel.recording_panel.start_recording_button.clicked.connect(
            lambda: self._client.start_recording(StartRecordingRequest(mic_device_index=self._skellycam_camera_panel.recording_panel.audio_recording_panel.user_selected_mic_index,
                                                                       recording_name= self._skellycam_camera_panel.recording_panel.session_nametag.text().strip()))
        )

        self._skellycam_camera_panel.recording_panel.stop_recording_button.clicked.connect(
            self._client.stop_recording
        )

        self._control_panel.use_clientside_camera_detection.stateChanged.connect(
            self._save_gui_state
        )
        self._control_panel.connect_automatically_checkbox.stateChanged.connect(self._save_gui_state)

        #Keyboard Shortcuts
        # Connect signals to slots
        self.keyboard_shortcuts.number_pressed.connect(self._skellycam_camera_panel.set_selected_camera)
        self.keyboard_shortcuts.annotate_images.connect(self._skellycam_camera_panel.toggle_annotation)
        # self.keyboard_shortcuts.increase_exposure.connect(self._increase_selected_camera_exposure)
        # self.keyboard_shortcuts.decrease_exposure.connect(self._decrease_selected_camera_exposure)
        # self.keyboard_shortcuts.toggle_recording.connect(lambda: self.label.setText("Toggling recording"))
        # self.keyboard_shortcuts.pause.connect(lambda: self.label.setText("Pausing"))
        # self.keyboard_shortcuts.take_snapshot.connect(lambda: self.label.setText("Taking snapshot"))
        # self.keyboard_shortcuts.show_help.connect(self.show_help_dialog)

    def _hide_welcome_view(self):
        self._welcome_to_skellycam_widget.hide()
        self._welcome_connect_to_cameras_button.hide()
        self._skellycam_camera_panel.show()




    @Slot()
    def connect_to_cameras(self):
        self._hide_welcome_view()
        self._control_panel.apply_settings_to_cameras_button.setEnabled(True)
        self._control_panel.close_cameras_button.setEnabled(True)
        if self._control_panel.use_clientside_camera_detection.isChecked() and False: # Disable client-side detection for now
            if not self._control_panel.user_selected_camera_configs:
                self._control_panel.camera_settings_panel.update_camera_configs(get_available_cameras(CameraDetectionStrategies.QT_MULTIMEDIA))
                self._client.cameras_connect_apply(self._control_panel.user_selected_camera_configs)
            else:
                self._client.cameras_connect_detect()
        else:
            self._client.cameras_connect_detect()
        self._save_gui_state()


    @Slot()
    def close_cameras(self):
        self._control_panel.close_cameras_button.setEnabled(False)
        self._client.close_cameras()

    @Slot(object)
    def _handle_new_app_state(self, app_state: SkellycamAppStateDTO):
        self._control_panel.handle_new_app_state(app_state)
        self._skellycam_camera_panel.handle_new_app_state(app_state)

    def closeEvent(self, a0) -> None:

        logger.info("Closing QT GUI window")
        self._global_kill_flag.value = True
        try:
            self._skellycam_camera_panel.close()
        except Exception as e:
            logger.error(f"Error while closing the viewer widget: {e}")
        super().closeEvent(a0)

        remove_empty_directories(get_default_skellycam_base_folder_path())

    def _load_gui_state(self):
        """
        Load a previously saved GUI state from `~/.skellycam/gui_state.json`
        """
        pass
        # saved_gui_state = Path(GUI_STATE_FILE_PATH)
        # if saved_gui_state.exists():
        #     try:
        #         gui_state = GuiState.model_validate_json(saved_gui_state.read_text())
        #         self._control_panel.connect_automatically_checkbox.setChecked(gui_state.connect_automatically_checkbox)
        #         self._control_panel.use_clientside_camera_detection.setChecked(gui_state.use_clientside_camera_detection)
        #         self._control_panel.camera_settings_panel.update_camera_configs(gui_state.camera_configs)
        #     except Exception as e:
        #         logger.error(f"Error while loading GUI state: {e}")

    def _save_gui_state(self):
        """
        Save the current GUI state to `~/.skellycam/gui_state.json`
        """
        pass
        # saved_gui_state = Path(GUI_STATE_FILE_PATH)
        # gui_state = GuiState(connect_automatically_checkbox=self._control_panel.connect_automatically_checkbox.isChecked(),
        #                      use_clientside_camera_detection=self._control_panel.use_clientside_camera_detection.isChecked(),
        #                      camera_configs=self._control_panel.user_selected_camera_configs)
        # saved_gui_state.write_text(gui_state.model_dump_json())

def remove_empty_directories(root_dir: Union[str, Path]):
    """
    Recursively remove empty directories from the root directory
    :param root_dir: The root directory to start removing empty directories from
    """
    for path in Path(root_dir).rglob("*"):
        if path.is_dir() and not any(path.iterdir()):
            logger.gui(f"Removing empty directory: {path}")
            path.rmdir()
        elif path.is_dir() and any(path.iterdir()):
            remove_empty_directories(path)
        else:
            continue


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    main_window = SkellyCamMainWindow()
    main_window.show()
    app.exec()
    for process in multiprocessing.active_children():
        logger.gui(f"Terminating process: {process}")
        process.terminate()
    sys.exit()
