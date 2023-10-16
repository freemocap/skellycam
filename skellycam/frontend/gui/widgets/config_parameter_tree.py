from copy import deepcopy
from typing import Dict, Union

from PySide6.QtWidgets import QVBoxLayout, QWidget, QMainWindow
from pyqtgraph.parametertree import ParameterTree, Parameter

from skellycam import logger
from skellycam.data_models.cameras.camera_config import CameraConfig, RotationType
from skellycam.data_models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.data_models.cameras.video_resolution import VideoResolution
from skellycam.data_models.request_response_update import UpdateCameraConfigs
from skellycam.frontend.gui.utilities.qt_strings import (COPY_SETTINGS_TO_CAMERAS_STRING,
                                                         rotate_image_str_to_cv2_code,
                                                         USE_THIS_CAMERA_STRING)
from skellycam.frontend.gui.widgets._update_widget_template import UpdateWidget
from skellycam.frontend.gui.widgets.camera_control_panel import CameraControlPanelView


class CameraSettingsView(UpdateWidget):

    def __init__(self, parent: Union[QMainWindow, 'UpdateWidget', QWidget]):
        super().__init__(parent=parent)
        self._parameter_groups = None
        self._camera_control_panel_view = CameraControlPanelView(parent=self)
        self._parameter_tree = ParameterTree(parent=self, showHeader=False)

        self.initUI()

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

    @property
    def camera_configs(self) -> Dict[str, CameraConfig]:
        return self._extract_camera_configs()

    def update_parameter_tree(self, available_cameras: Dict[str, CameraDeviceInfo]):
        logger.debug("Updating camera configs in parameter tree")
        camera_configs = {camera_id: CameraConfig(camera_id=camera_id) for camera_id in available_cameras.keys()}
        self._parameter_tree.clear()
        self._parameter_groups = {}
        for camera_config in camera_configs.values():
            self._parameter_groups[camera_config.camera_id] = self._convert_to_parameter(camera_config)
            self._parameter_tree.addParameters(self._parameter_groups[camera_config.camera_id])

    def _convert_to_parameter(self, camera_config: CameraConfig) -> Parameter:

        camera_parameter_group = Parameter.create(
            name="Camera_" + str(camera_config.camera_id),
            type="group",
            children=[
                dict(name=self.tr(USE_THIS_CAMERA_STRING),
                     type="bool",
                     value=True),
                dict(
                    name=self.tr("Rotate Image"),
                    type="list",
                    limits=RotationType.as_strings(),
                    value=camera_config.rotation.value,
                ),
                dict(name=self.tr("Exposure"),
                     type="int",
                     value=camera_config.exposure),
                dict(
                    name=self.tr("Resolution Width"),
                    type="int",
                    value=camera_config.resolution.width,
                ),
                dict(
                    name=self.tr("Resolution Height"),
                    type="int",
                    value=camera_config.resolution.height,
                ),
                dict(
                    name="FourCC",
                    type="str",
                    value=camera_config.fourcc,
                ),
                dict(
                    name=self.tr("Framerate"),
                    type="int",
                    value=camera_config.framerate,
                    tip="Framerate in frames per second",
                ),
                self._create_copy_to_all_cameras_action_parameter(
                    camera_id=camera_config.camera_id
                ),
            ],
        )

        camera_parameter_group.param(self.tr(USE_THIS_CAMERA_STRING)).sigValueChanged.connect(
            lambda: self._enable_or_disable_camera_settings(camera_parameter_group)
        )
        camera_parameter_group.sigValueChanged.connect(
            lambda _: self.emit_message(UpdateCameraConfigs(data=self.camera_configs)
                                        )
        )
        return camera_parameter_group

    def _create_copy_to_all_cameras_action_parameter(self, camera_id) -> Parameter:
        button = Parameter.create(
            name=self.tr(COPY_SETTINGS_TO_CAMERAS_STRING),
            type="action",
        )
        button.sigActivated.connect(
            lambda: self._apply_settings_to_all_cameras(camera_id)
        )
        return button

    def _extract_camera_configs(self) -> Dict[str, CameraConfig]:
        logger.info("Extracting camera configs from parameter tree")
        configs = {}
        for (camera_id, parameter_group,) in self._parameter_groups.items():
            configs[camera_id] = CameraConfig(
                camera_id=camera_id,
                exposure=parameter_group.param(self.tr("Exposure")).value(),
                resolution=VideoResolution(width=parameter_group.param(self.tr("Resolution Width")).value(),
                                           height=parameter_group.param(self.tr("Resolution Height")).value()),
                framerate=parameter_group.param(self.tr("Framerate")).value(),
                fourcc=parameter_group.param("FourCC").value(),
                rotate_video_cv2_code=rotate_image_str_to_cv2_code(
                    parameter_group.param(self.tr("Rotate Image")).value()
                ),
                use_this_camera=parameter_group.param(self.tr(USE_THIS_CAMERA_STRING)).value(),
            )

        return configs

    def _apply_settings_to_all_cameras(self, camera_id_to_copy_from: str):
        logger.info(f"Applying settings to all cameras from camera {camera_id_to_copy_from}")

        for camera_id in self.camera_configs.keys():
            original_config = deepcopy(self.camera_configs[camera_id])
            self.camera_configs[camera_id] = deepcopy(self.camera_configs[camera_id_to_copy_from])
            self.camera_configs[camera_id].camera_id = camera_id
            self.camera_configs[camera_id].use_this_camera = original_config.use_this_camera
        self.update_parameter_tree()

    def _enable_or_disable_camera_settings(self, camera_config_parameter_group):
        use_this_camera_checked = camera_config_parameter_group.param(
            USE_THIS_CAMERA_STRING
        ).value()
        for child_parameter in camera_config_parameter_group.children():
            if child_parameter.name() != USE_THIS_CAMERA_STRING:
                child_parameter.setOpts(enabled=use_this_camera_checked)
                child_parameter.setReadonly(use_this_camera_checked)
