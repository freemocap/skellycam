import logging
from copy import deepcopy
from typing import Dict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget
from pyqtgraph.parametertree import Parameter, ParameterTree

from skellycam.gui.qt.skelly_cam_widget import SkellyCamWidget
from skellycam.gui.qt.utilities.qt_label_strings import (COLLAPSE_ALL_STRING, COPY_SETTINGS_TO_CAMERAS_STRING,
                                                         EXPAND_ALL_STRING, ROTATE_180_STRING,
                                                         ROTATE_90_CLOCKWISE_STRING, ROTATE_90_COUNTERCLOCKWISE_STRING,
                                                         rotate_cv2_code_to_str, rotate_image_str_to_cv2_code,
                                                         USE_THIS_CAMERA_STRING)
from skellycam.opencv.camera.models.camera_config import CameraConfig
from skellycam.system.environment.default_paths import RED_X_EMOJI_STRING, MAGNIFYING_GLASS_EMOJI_STRING, \
    CAMERA_WITH_FLASH_EMOJI_STRING, HAMMER_AND_WRENCH_EMOJI_STRING

logger = logging.getLogger(__name__)


#
# parameter_tree_stylesheet_string = """
#                                     QTreeView {
#                                         background-color: rgb(0, 152, 154);
#                                         alternate-background-color: rgb(139, 144, 145);
#                                         color: rgb(28, 100, 28);
#                                     }
#                                     QLabel {
#                                         color: rgb(28, 123, 28);
#                                     }
#                                     QPushbutton {
#                                         color: rgb(0, 28, 8);
#                                     }
#                                     QTreeView::item:has-children {
#                                         background-color: '#212627';
#                                         color: rgb(233, 185, 110);
#                                     }
#                                     QTreeView::item:selected {
#                                         background-color: rgb(92, 53, 102);
#                                     }
#                                     QTreeView::item:selected:active {
#                                         background-color: rgb(92, 53, 102);
#                                     }
#                                     """


class SkellyCamParameterTreeWidget(QWidget):
    emitting_camera_configs_signal = Signal(dict)

    def __init__(self,
                 camera_viewer_widget: SkellyCamWidget):

        super().__init__()

        # self.setMinimumWidth(250)
        self.sizePolicy().setVerticalStretch(1)
        self.sizePolicy().setHorizontalStretch(1)


        self._camera_viewer_widget = camera_viewer_widget
        self.setStyleSheet("""
        QPushButton{
        border-width: 2px;
        font-size: 15px;
        }
        """)

        self._camera_parameter_group_dictionary = {}
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._close_cameras_button = QPushButton(f"Close Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{RED_X_EMOJI_STRING}")
        self._layout.addWidget(self._close_cameras_button)
        self._close_cameras_button.setEnabled(False)

        self._detect_available_cameras_button = QPushButton(f"Detect Available Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{MAGNIFYING_GLASS_EMOJI_STRING}")
        self._layout.addWidget(self._detect_available_cameras_button)
        self._detect_available_cameras_button.setEnabled(False)
        self._detect_available_cameras_button.clicked.connect(self._camera_viewer_widget.detect_available_cameras)

        self._apply_settings_to_cameras_button = QPushButton(
            f"Apply settings to cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{HAMMER_AND_WRENCH_EMOJI_STRING}",
        )
        self._apply_settings_to_cameras_button.clicked.connect(
            self._emit_camera_configs_dict
        )
        self._apply_settings_to_cameras_button.setEnabled(False)
        self._layout.addWidget(self._apply_settings_to_cameras_button)

        self._parameter_tree_widget = ParameterTree(parent=self, showHeader=False)
        # self._parameter_tree_widget.setStyleSheet(parameter_tree_stylesheet_string)
        self._layout.addWidget(self._parameter_tree_widget)
        self._parameter_tree_widget.addParameters(
            Parameter(name="No cameras connected...", value="", type="str")
        )

        self._connect_signals_to_slots(self._camera_viewer_widget)

    def _connect_signals_to_slots(self, camera_viewer_widget: SkellyCamWidget):
        camera_viewer_widget.camera_group_created_signal.connect(
            self.update_camera_config_parameter_tree
        )

        self.emitting_camera_configs_signal.connect(
            camera_viewer_widget.update_camera_configs
        )

        self._close_cameras_button.clicked.connect(
            self._handle_close_cameras_button_clicked
        )
        self._camera_viewer_widget.cameras_connected_signal.connect(
            lambda: self._close_cameras_button.setEnabled(True)
        )
        self._camera_viewer_widget.cameras_connected_signal.connect(
            lambda: self._detect_available_cameras_button.setEnabled(True)
        )

        self._camera_viewer_widget.cameras_connected_signal.connect(
            lambda: self._apply_settings_to_cameras_button.setEnabled(True)
        )

    def update_camera_config_parameter_tree(
            self, dictionary_of_camera_configs: Dict[str, CameraConfig]
    ):
        logger.info("Updating camera configs in parameter tree")

        self._parameter_tree_widget.clear()
        self._add_expand_collapse_buttons()
        for camera_config in dictionary_of_camera_configs.values():
            self._camera_parameter_group_dictionary[
                camera_config.camera_id
            ] = self._convert_camera_config_to_parameter(camera_config)
            self._parameter_tree_widget.addParameters(
                self._camera_parameter_group_dictionary[camera_config.camera_id]
            )

    def _emit_camera_configs_dict(self):
        camera_configs_dictionary = self._extract_dictionary_of_camera_configs()
        logger.info(f"Emitting camera configs dictionary: {camera_configs_dictionary}")
        self.emitting_camera_configs_signal.emit(camera_configs_dictionary)

    def _convert_camera_config_to_parameter(
            self, camera_config: CameraConfig
    ) -> Parameter:

        camera_parameter_group = Parameter.create(
            name="Camera_" + str(camera_config.camera_id),
            type="group",
            children=[
                dict(name=USE_THIS_CAMERA_STRING, type="bool", value=True),
                dict(
                    name="Rotate Image",
                    type="list",
                    limits=[
                        "None",
                        ROTATE_90_CLOCKWISE_STRING,
                        ROTATE_90_COUNTERCLOCKWISE_STRING,
                        ROTATE_180_STRING,
                    ],
                    value=rotate_cv2_code_to_str(camera_config.rotate_video_cv2_code),
                ),
                dict(
                    name="Exposure", 
                    type="str", 
                    value=camera_config.exposure
                ),
                dict(
                    name="Resolution Width",
                    type="int",
                    value=camera_config.resolution_width,
                ),
                dict(
                    name="Resolution Height",
                    type="int",
                    value=camera_config.resolution_height,
                ),
                dict(
                    name="FourCC",
                    type="str",
                    value=camera_config.fourcc,
                ),
                dict(
                    name="Framerate",
                    type="int",
                    value=camera_config.framerate,
                    tip="Framerate in frames per second",
                ),
                self._create_copy_to_all_cameras_action_parameter(
                    camera_id=camera_config.camera_id
                ),
            ],
        )

        camera_parameter_group.param(USE_THIS_CAMERA_STRING).sigValueChanged.connect(
            lambda: self._enable_or_disable_camera_settings(camera_parameter_group)
        )

        return camera_parameter_group

    def _create_copy_to_all_cameras_action_parameter(self, camera_id) -> Parameter:
        button = Parameter.create(
            name=COPY_SETTINGS_TO_CAMERAS_STRING,
            type="action",
        )
        button.sigActivated.connect(
            lambda: self._apply_settings_to_all_cameras(camera_id)
        )
        return button

    def _extract_dictionary_of_camera_configs(self) -> Dict[str, CameraConfig]:
        logger.info("Extracting camera configs from parameter tree")
        camera_config_dictionary = {}
        for (
                camera_id,
                camera_parameter_group,
        ) in self._camera_parameter_group_dictionary.items():
            camera_config_dictionary[camera_id] = CameraConfig(
                camera_id=camera_id,
                exposure=camera_parameter_group.param("Exposure").value(),
                resolution_width=camera_parameter_group.param(
                    "Resolution Width"
                ).value(),
                resolution_height=camera_parameter_group.param(
                    "Resolution Height"
                ).value(),
                framerate=camera_parameter_group.param("Framerate").value(),
                fourcc=camera_parameter_group.param("FourCC").value(),
                rotate_video_cv2_code=rotate_image_str_to_cv2_code(
                    camera_parameter_group.param("Rotate Image").value()
                ),
                use_this_camera=camera_parameter_group.param(
                    USE_THIS_CAMERA_STRING
                ).value(),
            )
        return camera_config_dictionary

    def _apply_settings_to_all_cameras(self, camera_id_to_copy_from: str):
        logger.info(
            f"Applying settings to all cameras from camera {camera_id_to_copy_from}"
        )
        camera_config_dictionary = self._extract_dictionary_of_camera_configs()
        camera_config_to_copy_from = deepcopy(
            camera_config_dictionary[camera_id_to_copy_from]
        )

        for camera_id in camera_config_dictionary.keys():
            original_camera_config_dictionary = deepcopy(
                camera_config_dictionary[camera_id]
            )
            camera_config_dictionary[camera_id] = deepcopy(camera_config_to_copy_from)
            camera_config_dictionary[camera_id].camera_id = camera_id
            camera_config_dictionary[
                camera_id
            ].use_this_camera = original_camera_config_dictionary.use_this_camera

        self.update_camera_config_parameter_tree(camera_config_dictionary)

    def _enable_or_disable_camera_settings(self, camera_config_parameter_group):
        use_this_camera_checked = camera_config_parameter_group.param(
            USE_THIS_CAMERA_STRING
        ).value()
        for child_parameter in camera_config_parameter_group.children():
            if child_parameter.name() != USE_THIS_CAMERA_STRING:
                child_parameter.setOpts(enabled=use_this_camera_checked)
                child_parameter.setReadonly(use_this_camera_checked)

    def _add_expand_collapse_buttons(self):

        expand_all_button_parameter = Parameter.create(
            name=EXPAND_ALL_STRING, type="action"
        )
        expand_all_button_parameter.sigActivated.connect(
            self._expand_or_collapse_all_action
        )
        self._parameter_tree_widget.addParameters(expand_all_button_parameter)

        collapse_all_button_parameter = Parameter.create(
            name=COLLAPSE_ALL_STRING, type="action"
        )
        collapse_all_button_parameter.sigActivated.connect(
            self._expand_or_collapse_all_action
        )
        self._parameter_tree_widget.addParameters(collapse_all_button_parameter)

    def _expand_or_collapse_all_action(self, action):
        for camera_parameter in self._camera_parameter_group_dictionary.values():
            if action.name() == EXPAND_ALL_STRING:
                camera_parameter.setOpts(expanded=True)
            elif action.name() == COLLAPSE_ALL_STRING:
                camera_parameter.setOpts(expanded=False)

    def _handle_close_cameras_button_clicked(self):
        self._camera_viewer_widget.disconnect_from_cameras()


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    qt_camera_config_parameter_tree_widget = SkellyCamParameterTreeWidget(camera_viewer_widget=SkellyCamWidget())
    qt_camera_config_parameter_tree_widget.update_camera_config_parameter_tree(
        {"0": CameraConfig(camera_id=0), "1": CameraConfig(camera_id=1)}
    )
    qt_camera_config_parameter_tree_widget.show()
    sys.exit(app.exec())
