from copy import deepcopy
from typing import Dict, Union

from PySide6.QtWidgets import QVBoxLayout, QPushButton, QWidget, QMainWindow
from pyqtgraph.parametertree import ParameterTree, Parameter

from skellycam import logger
from skellycam.data_models.cameras.camera_config import CameraConfig
from skellycam.data_models.request_response_update import Request, RequestType
from skellycam.frontend.gui.utilities.qt_label_strings import (COLLAPSE_ALL_STRING, COPY_SETTINGS_TO_CAMERAS_STRING,
                                                               EXPAND_ALL_STRING, ROTATE_180_STRING,
                                                               ROTATE_90_CLOCKWISE_STRING,
                                                               ROTATE_90_COUNTERCLOCKWISE_STRING,
                                                               rotate_cv2_code_to_str, rotate_image_str_to_cv2_code,
                                                               USE_THIS_CAMERA_STRING)
from skellycam.frontend.gui.widgets._update_widget_template import UpdateWidget
from skellycam.system.environment.default_paths import RED_X_EMOJI_STRING, MAGNIFYING_GLASS_EMOJI_STRING, \
    CAMERA_WITH_FLASH_EMOJI_STRING, CLOCKWISE_VERTICAL_ARROWS_EMOJI_STRING

DETECT_AVAILABLE_CAMERAS_BUTTON_TEXT = f"Detect Available Cameras {MAGNIFYING_GLASS_EMOJI_STRING}"
CONNECT_TO_CAMERAS_BUTTON_TEXT = f"Connect to Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}"
RESET_CAMERA_SETTINGS_BUTTON_TEXT = f"Reset Camera Settings {CLOCKWISE_VERTICAL_ARROWS_EMOJI_STRING}"
CLOSE_CAMERAS_BUTTON_TEXT = f"Close Cameras {RED_X_EMOJI_STRING}"


class CameraControlPanelView(UpdateWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._layout = QVBoxLayout()

        self._detect_available_cameras_button = QPushButton(self.tr(DETECT_AVAILABLE_CAMERAS_BUTTON_TEXT))
        self._connect_to_cameras = QPushButton(self.tr(CONNECT_TO_CAMERAS_BUTTON_TEXT))
        self._close_cameras_button = QPushButton(self.tr(CLOSE_CAMERAS_BUTTON_TEXT))

        self.initUI()

    def initUI(self):
        self._layout.addWidget(self._close_cameras_button)
        self._close_cameras_button.setEnabled(False)

        self._layout.addWidget(self._detect_available_cameras_button)
        self._detect_available_cameras_button.setEnabled(False)
        self._connect_buttons()

    def _connect_buttons(self):
        self._detect_available_cameras_button.clicked.connect(lambda:
                                                              self.emit_message(Request(
                                                                  request_type=RequestType.DETECT_AVAILABLE_CAMERAS)))
        self._connect_to_cameras.clicked.connect(lambda:
                                                    self.emit_message(Request(
                                                        request_type=RequestType.CONNECT_TO_CAMERAS)))
        self._close_cameras_button.clicked.connect(
            lambda: self.emit_message(Request(request_type=RequestType.CLOSE_CAMERAS)))


class CameraSettingsView(UpdateWidget):

    def __init__(self, camera_configs: Dict[str, CameraConfig], parent: Union[QMainWindow, 'UpdateWidget', QWidget]):
        super().__init__(parent=parent)
        self._camera_configs = camera_configs
        self._camera_control_panel_view = CameraControlPanelView(parent=self)
        self._parameter_tree = ParameterTree(parent=self, showHeader=False)
        self.initUI()
        self.update_parameter_tree()

    def get_camera_configs(self) -> Dict[str, CameraConfig]:
        self._parameter_tree.

    def initUI(self):
        # self.setMinimumWidth(250)
        self.sizePolicy().setVerticalStretch(1)
        self.sizePolicy().setHorizontalStretch(1)

        self.setStyleSheet("""
        QPushButton{
        border-width: 2px;
        font-size: 15px;
        }
        """)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._layout.addWidget(self._camera_control_panel_view)

        self._layout.addWidget(self._parameter_tree)

    def update_parameter_tree(self):

        logger.debug("Updating camera configs in parameter tree")

        self._parameter_tree.clear()
        self._add_expand_collapse_buttons()
        for camera_config in dictionary_of_camera_configs.values():
            self._camera_parameter_group_dictionary[
                camera_config.camera_id
            ] = self._convert_camera_config_to_parameter(camera_config)
            self._parameter_tree.addParameters(
                self._camera_parameter_group_dictionary[camera_config.camera_id]
            )

    def _emit_camera_configs_dict(self):
        camera_configs_dictionary = self._extract_dictionary_of_camera_configs()
        logger.info(f"Emitting camera configs dictionary: {camera_configs_dictionary}")

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
                dict(name="Exposure", type="int", value=camera_config.exposure),
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
        self._parameter_tree.addParameters(expand_all_button_parameter)

        collapse_all_button_parameter = Parameter.create(
            name=COLLAPSE_ALL_STRING, type="action"
        )
        collapse_all_button_parameter.sigActivated.connect(
            self._expand_or_collapse_all_action
        )
        self._parameter_tree.addParameters(collapse_all_button_parameter)

    def _expand_or_collapse_all_action(self, action):
        for camera_parameter in self._camera_parameter_group_dictionary.values():
            if action.name() == EXPAND_ALL_STRING:
                camera_parameter.setOpts(expanded=True)
            elif action.name() == COLLAPSE_ALL_STRING:
                camera_parameter.setOpts(expanded=False)
