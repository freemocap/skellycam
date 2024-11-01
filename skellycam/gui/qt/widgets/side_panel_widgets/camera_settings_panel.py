import logging
from copy import deepcopy
from typing import Optional

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QVBoxLayout, QWidget
from pyqtgraph.parametertree import ParameterTree, Parameter

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.camera_group.camera.config.image_resolution import ImageResolution
from skellycam.core.camera_group.camera.config.image_rotation_types import RotationTypes
from skellycam.gui.qt.utilities.qt_label_strings import USE_THIS_CAMERA_STRING, COPY_SETTINGS_TO_CAMERAS_STRING
from skellycam.system.device_detection.camera_device_info import CameraDeviceInfo, AvailableDevices

logger = logging.getLogger(__name__)


class CameraSettingsPanel(QWidget):

    def __init__(self, parent: QWidget):
        super().__init__(parent=parent)

        self._user_selected_camera_configs: Optional[CameraConfigs] = None
        self._app_state_camera_configs: Optional[CameraConfigs] = None
        self._available_devices: Optional[AvailableDevices] = None

        self._parameter_groups = {}

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
        self._parameter_tree = ParameterTree(parent=self, showHeader=False)
        self._layout.addWidget(self._parameter_tree)

    @property
    def user_selected_camera_configs(self) -> Optional[CameraConfigs]:
        self._update_user_selected_camera_settings()
        return self._user_selected_camera_configs

    @Slot(object)
    def update_available_devices(self, available_devices: AvailableDevices):
        logger.gui("Updating Camera Parameter Tree")
        if self._available_devices == available_devices:
            return
        self._available_devices = available_devices
        if not self._available_devices or len(self._available_devices) == 0:
            return
        if not self._user_selected_camera_configs or len(self._user_selected_camera_configs) == 0:
            self._user_selected_camera_configs = {camera_id: CameraConfig(camera_id=camera_id)
                                                  for camera_id in self._available_devices.keys()}

        if len(self._parameter_groups) > 0:
            self._parameter_tree.clear()
        self._parameter_groups = {}
        for camera_config, camera_info in zip(self._user_selected_camera_configs.values(),
                                              self._available_devices.values()):
            self._parameter_groups[camera_config.camera_id] = self._convert_to_parameter(camera_config=camera_config,
                                                                                         camera_info=camera_info)
            self._parameter_tree.addParameters(self._parameter_groups[camera_config.camera_id])

    def _convert_to_parameter(self, camera_config: CameraConfig,
                              camera_info: CameraDeviceInfo) -> Parameter:
        logger.gui(f"Converting camera config to parameter: {camera_config}")
        # Retrieve the descriptions from the CameraConfig class
        config_schema = camera_config.model_fields
        camera_parameter_group = Parameter.create(
            name="Camera_" + str(camera_config.camera_id),
            type="group",
            children=[
                dict(name=self.tr(USE_THIS_CAMERA_STRING),
                     type="bool",
                     value=True,
                     tip=config_schema['use_this_camera'].description,
                        ),
                dict(
                    name=self.tr("Rotate"),
                    type="list",
                    limits=[rotation_type.name for rotation_type in RotationTypes],
                    value=camera_config.rotation.name,
                    tip=config_schema['rotation'].description,
                ),
                dict(
                    name=self.tr("Exposure"),
                    type="list",
                    limits=["AUTO" , *[str(x) for x in range(-4, -13, -1)]],
                    value=str(camera_config.exposure),
                    tip=config_schema['exposure'].description,
                ),
                dict(
                    name=self.tr("Resolution"),
                    type="list",
                    limits=camera_info.available_resolutions,
                    value=str(camera_config.resolution),
                ),
                dict(
                    name=self.tr("Framerate"),
                    type="list",
                    value=camera_config.framerate,
                    limits=camera_info.available_framerates,
                    tip=config_schema['framerate'].description,
                ),
                dict(
                    name=self.tr("Video Capture FourCC"),
                    type="str",
                    value=camera_config.capture_fourcc,
                    tip=config_schema['capture_fourcc'].description,
                ),
                dict(
                    name=self.tr("Video Writer FourCC"),
                    type="str",
                    value=camera_config.writer_fourcc,
                    tip=config_schema['writer_fourcc'].description,
                ),

                self._create_copy_to_all_cameras_action_parameter(
                    camera_id=camera_config.camera_id
                ),
            ],
        )

        # camera_parameter_group.param(self.tr(USE_THIS_CAMERA_STRING)).sigValueChanged.connect(
        #     lambda: self._enable_or_disable_camera_settings(camera_parameter_group)
        # )
        camera_parameter_group.sigTreeStateChanged.connect(self._update_user_selected_camera_settings)
        return camera_parameter_group

    def _create_copy_to_all_cameras_action_parameter(self, camera_id) -> Parameter:
        button = Parameter.create(
            name=self.tr(COPY_SETTINGS_TO_CAMERAS_STRING),
            type="action",
        )
        button.sigActivated.connect(
            lambda: self._copy_settings_to_all_cameras(camera_id)
        )
        return button

    def _update_user_selected_camera_settings(self):
        logger.gui("Extracting camera configs from parameter tree")
        new_user_selected_configs = {}
        for (camera_id, parameter_group,) in self._parameter_groups.items():
            if not parameter_group.param(USE_THIS_CAMERA_STRING).value():
                continue
            new_user_selected_configs[camera_id] = CameraConfig(
                camera_id=camera_id,
                use_this_camera=parameter_group.param(USE_THIS_CAMERA_STRING).value(),
                resolution=ImageResolution.from_string(parameter_group.param("Resolution").value()),
                exposure=parameter_group.param("Exposure").value(),
                framerate=parameter_group.param("Framerate").value(),
                capture_fourcc=parameter_group.param("Video Capture FourCC").value(),
                writer_fourcc=parameter_group.param("Video Writer FourCC").value(),
                rotation=RotationTypes[parameter_group.param("Rotate").value()],
            )
        self._user_selected_camera_configs = new_user_selected_configs

    def _copy_settings_to_all_cameras(self, camera_id_to_copy_from: CameraId):
        logger.gui(f"Applying settings to all cameras from camera {camera_id_to_copy_from}")
        camera_configs = self._user_selected_camera_configs
        for camera_id in camera_configs.keys():
            if camera_id == camera_id_to_copy_from:
                continue
            original_config = deepcopy(self._user_selected_camera_configs[camera_id])
            camera_configs[camera_id] = deepcopy(self._user_selected_camera_configs[camera_id_to_copy_from])
            camera_configs[camera_id].camera_id = camera_id
            camera_configs[camera_id].use_this_camera = original_config.use_this_camera
        self._update_user_selected_camera_settings()

    def _enable_or_disable_camera_settings(self, camera_config_parameter_group):
        use_this_camera_checked = camera_config_parameter_group.param(
            USE_THIS_CAMERA_STRING
        ).value()
        for child_parameter in camera_config_parameter_group.children():
            if child_parameter.name() != USE_THIS_CAMERA_STRING:
                child_parameter.setOpts(enabled=use_this_camera_checked)
                child_parameter.setReadonly(use_this_camera_checked)
