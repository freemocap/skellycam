import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from skellycam.gui.gui_state import get_gui_state
from skellycam.gui.qt.skelly_cam_widget import SkellyCamWidget
from skellycam.gui.qt.widgets.side_panel_widgets.camera_settings_panel import CameraSettingsPanel
from skellycam.system.default_paths import CAMERA_WITH_FLASH_EMOJI_STRING, RED_X_EMOJI_STRING, \
    MAGNIFYING_GLASS_EMOJI_STRING, HAMMER_AND_WRENCH_EMOJI_STRING, SPARKLES_EMOJI_STRING

logger = logging.getLogger(__name__)


class SkellyCamControlPanel(QWidget):
    emitting_camera_configs_signal = Signal(dict)

    def __init__(self,
                 skellycam_widget: SkellyCamWidget):
        super().__init__()

        self.gui_state = get_gui_state()
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
        self.detect_available_cameras_button.clicked.connect(self._skellycam_widget.detect_available_cameras)
        self._layout.addWidget(self.detect_available_cameras_button)

        self.connect_cameras_button = QPushButton(
            f"Connect Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{SPARKLES_EMOJI_STRING}")
        self._layout.addWidget(self.connect_cameras_button)
        self.connect_cameras_button.clicked.connect(self._skellycam_widget.connect_to_cameras)

        self.apply_settings_to_cameras_button = QPushButton(
            f"Apply settings to cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{HAMMER_AND_WRENCH_EMOJI_STRING}",
        )
        self.apply_settings_to_cameras_button.clicked.connect(self._skellycam_widget.apply_settings_to_cameras)
        self._layout.addWidget(self.apply_settings_to_cameras_button)

        self._close_cameras_button = QPushButton(f"Close Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{RED_X_EMOJI_STRING}")
        self._layout.addWidget(self._close_cameras_button)
        self._close_cameras_button.clicked.connect(self._skellycam_widget.close_cameras)

        self._parameter_tree_widget = CameraSettingsPanel(parent=self)
        self._layout.addWidget(self._parameter_tree_widget)

    def update_widget(self):
        
        logger.trace(f"Updating {self.__class__.__name__}")
        self._parameter_tree_widget.update_widget()
