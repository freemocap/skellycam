import logging
from copy import deepcopy

from PySide6.QtWidgets import QVBoxLayout, QWidget
from pyqtgraph.parametertree import ParameterTree, Parameter

from skellycam.core import CameraId
from skellycam.core.cameras.camera.config.camera_config import CameraConfig
from skellycam.core.cameras.camera.config.image_resolution import ImageResolution
from skellycam.core.cameras.camera.config.image_rotation_types import RotationTypes
from skellycam.core.detection.camera_device_info import CameraDeviceInfo
from skellycam.gui.gui_state import get_gui_state
from skellycam.gui.qt.utilities.qt_label_strings import USE_THIS_CAMERA_STRING, COPY_SETTINGS_TO_CAMERAS_STRING

logger = logging.getLogger(__name__)


class CameraSettingsPanel(QWidget):

    def __init__(self, parent: QWidget):
        super().__init__(parent=parent)
        self._gui_state = get_gui_state()
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

    def update_parameter_tree(self):
        logger.debug("Updating Camera Parameter Tree")
        available_devices = self._gui_state.available_devices
        camera_configs = self._gui_state.camera_configs
        if len(camera_configs) == 0:
            return
        if len(self._parameter_groups) > 0:
            self._parameter_tree.clear()
        self._parameter_groups = {}
        for camera_config, camera_info in zip(camera_configs.values(), available_devices.values()):
            self._parameter_groups[camera_config.camera_id] = self._convert_to_parameter(camera_config=camera_config,
                                                                                         camera_info=camera_info)
            self._parameter_tree.addParameters(self._parameter_groups[camera_config.camera_id])

    def update_gui_state(self):
        self._gui_state.camera_configs = self._extract_camera_configs_from_tree()

    def _convert_to_parameter(self, camera_config: CameraConfig,
                              camera_info: CameraDeviceInfo) -> Parameter:
        logger.debug(f"Converting camera config to parameter: {camera_config}")
        camera_parameter_group = Parameter.create(
            name="Camera_" + str(camera_config.camera_id),
            type="group",
            children=[
                dict(name=self.tr(USE_THIS_CAMERA_STRING),
                     type="bool",
                     value=True),
                dict(
                    name=self.tr("Rotate"),
                    type="list",
                    limits=[rotation_type.name for rotation_type in RotationTypes],
                    value=camera_config.rotation.name,
                ),
                dict(name=self.tr("Exposure"),
                     type="int",
                     limits=(-13, -1),
                     value=camera_config.exposure),
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
                    tip="Framerate in frames per second",
                ),
                dict(
                    name=self.tr("Video Capture FourCC"),
                    type="str",
                    value=camera_config.capture_fourcc,
                ),
                dict(
                    name=self.tr("Video Writer FourCC"),
                    type="str",
                    value=camera_config.writer_fourcc,
                ),

                self._create_copy_to_all_cameras_action_parameter(
                    camera_id=camera_config.camera_id
                ),
            ],
        )

        camera_parameter_group.param(self.tr(USE_THIS_CAMERA_STRING)).sigValueChanged.connect(
            lambda: self._enable_or_disable_camera_settings(camera_parameter_group)
        )
        camera_parameter_group.sigTreeStateChanged.connect(self._extract_camera_configs_from_tree)
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

    def _extract_camera_configs_from_tree(self):
        logger.info("Extracting camera configs from parameter tree")
        self._camera_configs = {}
        for (camera_id, parameter_group,) in self._parameter_groups.items():
            self._camera_configs[camera_id] = CameraConfig(
                camera_id=camera_id,
                use_this_camera=parameter_group.param(USE_THIS_CAMERA_STRING).value(),
                resolution=ImageResolution.from_string(parameter_group.param("Resolution").value()),
                exposure=parameter_group.param("Exposure").value(),
                framerate=parameter_group.param("Framerate").value(),
                capture_fourcc=parameter_group.param("Video Capture FourCC").value(),
                writer_fourcc=parameter_group.param("Video Writer FourCC").value(),
                rotation=RotationTypes[parameter_group.param("Rotate").value()],
            )

    def _copy_settings_to_all_cameras(self, camera_id_to_copy_from: CameraId):
        logger.info(f"Applying settings to all cameras from camera {camera_id_to_copy_from}")
        camera_configs = self._gui_state.camera_configs
        for camera_id in camera_configs.keys():
            if camera_id == camera_id_to_copy_from:
                continue
            original_config = deepcopy(self._camera_configs[camera_id])
            camera_configs[camera_id] = deepcopy(self._camera_configs[camera_id_to_copy_from])
            camera_configs[camera_id].camera_id = camera_id
            camera_configs[camera_id].use_this_camera = original_config.use_this_camera
        self._gui_state.camera_configs = camera_configs

    def _enable_or_disable_camera_settings(self, camera_config_parameter_group):
        use_this_camera_checked = camera_config_parameter_group.param(
            USE_THIS_CAMERA_STRING
        ).value()
        for child_parameter in camera_config_parameter_group.children():
            if child_parameter.name() != USE_THIS_CAMERA_STRING:
                child_parameter.setOpts(enabled=use_this_camera_checked)
                child_parameter.setReadonly(use_this_camera_checked)

    # def _handle_parameter_tree_change(self):
    #     logger.trace(f"Parameter tree changed -  emitting camera_configs_changed signal")
    #     self.camera_configs_changed.emit(self.camera_configs)
