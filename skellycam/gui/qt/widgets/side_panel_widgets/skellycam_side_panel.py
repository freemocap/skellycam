import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from skellycam.gui.gui_state import get_gui_state
from skellycam.gui.qt.skelly_cam_widget import SkellyCamWidget
from skellycam.gui.qt.widgets.side_panel_widgets.camera_parameter_tree import CameraParameterTree
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
        self._make_buttons()

        self._parameter_tree_widget = CameraParameterTree(parent=self)
        self._layout.addWidget(self._parameter_tree_widget)
        self._apply_settings_to_cameras_button.clicked.connect(self._parameter_tree_widget.update_gui_state)

    def update(self):
        self._parameter_tree_widget.update_parameter_tree()

    def _make_buttons(self):
        self._detect_available_cameras_button = QPushButton(
            f"Detect Available Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{MAGNIFYING_GLASS_EMOJI_STRING}")
        self._detect_available_cameras_button.clicked.connect(self._skellycam_widget.detect_available_cameras)
        self._layout.addWidget(self._detect_available_cameras_button)

        self._detect_available_cameras_button.clicked.connect(self._skellycam_widget.detect_available_cameras)
        self._connect_cameras_button = QPushButton(
            f"Connect Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{SPARKLES_EMOJI_STRING}")
        self._layout.addWidget(self._connect_cameras_button)
        # self._close_cameras_button.setEnabled(False)
        self._apply_settings_to_cameras_button = QPushButton(
            f"Apply settings to cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{HAMMER_AND_WRENCH_EMOJI_STRING}",
        )

        self._layout.addWidget(self._apply_settings_to_cameras_button)
        self._close_cameras_button = QPushButton(f"Close Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{RED_X_EMOJI_STRING}")
        self._layout.addWidget(self._close_cameras_button)