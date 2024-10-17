import logging

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget
from skellycam.app.app_state import AppStateDTO

from skellycam.core.detection.camera_device_info import AvailableDevices
from skellycam.gui.qt.camera_panel import CameraPanel
from skellycam.gui.qt.widgets.side_panel_widgets.camera_settings_panel import CameraSettingsPanel
from skellycam.system.default_paths import CAMERA_WITH_FLASH_EMOJI_STRING, RED_X_EMOJI_STRING, \
    MAGNIFYING_GLASS_EMOJI_STRING, HAMMER_AND_WRENCH_EMOJI_STRING, SPARKLES_EMOJI_STRING

logger = logging.getLogger(__name__)


class CameraControlPanel(QWidget):
    emitting_camera_configs_signal = Signal(dict)

    def __init__(self,
                 skellycam_widget: CameraPanel):
        super().__init__()

        # self.setMinimumWidth(250)

        self.sizePolicy().setVerticalStretch(1)
        self.sizePolicy().setHorizontalStretch(1)

        self._skellycam_widget = skellycam_widget
        self.setStyleSheet("""
        QPushButton{
        border-width: 2px;
        font-size: 15px;
        }
        """)

        self._camera_parameter_groups = {}
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        # Make Buttons
        self.detect_available_cameras_button = QPushButton(
            f"Detect Available Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{MAGNIFYING_GLASS_EMOJI_STRING}")
        self._layout.addWidget(self.detect_available_cameras_button)

        self.connect_cameras_button = QPushButton(
            f"Connect Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{SPARKLES_EMOJI_STRING}")
        self._layout.addWidget(self.connect_cameras_button)
        self.connect_cameras_button.clicked.connect(self._skellycam_widget.connect_to_cameras)

        self.apply_settings_to_cameras_button = QPushButton(
            f"Apply settings to cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{HAMMER_AND_WRENCH_EMOJI_STRING}",
        )
        self.apply_settings_to_cameras_button.setEnabled(False)
        self._layout.addWidget(self.apply_settings_to_cameras_button)

        self.close_cameras_button = QPushButton(f"Close Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{RED_X_EMOJI_STRING}")
        self.close_cameras_button.setEnabled(False)
        self._layout.addWidget(self.close_cameras_button)

        # Camera Settings Panel
        self._camera_settings_panel = CameraSettingsPanel(parent=self)
        self._layout.addWidget(self._camera_settings_panel)

    @property
    def user_selected_camera_configs(self):
        return self._camera_settings_panel.user_selected_camera_configs

    @Slot(object)
    def handle_new_app_state(self, app_state: AppStateDTO):
        if app_state.available_devices:
            self.apply_settings_to_cameras_button.setEnabled(True)
            self._camera_settings_panel.update_available_devices(app_state.available_devices)
        else:
            self.apply_settings_to_cameras_button.setEnabled(False)

        if app_state.camera_configs:
            self.close_cameras_button.setEnabled(True)
        else:
            self.close_cameras_button.setEnabled(False)

    # def update_widget(self):
    #
    #     logger.gui(f"Updating {self.__class__.__name__}")
    #     if self.gui_state.available_devices:
    #
    #     else:
    #         self._apply_settings_to_cameras_button.setEnabled(False)
    #
    #     if self.gui_state.connected_camera_configs:
    #         self._close_cameras_button.setEnabled(True)
    #     else:
    #         self._close_cameras_button.setEnabled(False)


