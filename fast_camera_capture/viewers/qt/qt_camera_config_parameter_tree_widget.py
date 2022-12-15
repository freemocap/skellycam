import logging
from typing import Dict

import cv2
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from pyqtgraph.parametertree import ParameterTree, Parameter

from fast_camera_capture import CameraConfig

logger = logging.getLogger(__name__)


class QtCameraConfigParameterTreeWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._apply_settings_to_cameras_button = QPushButton(
            "Apply settings to cameras",
        )
        self._apply_settings_to_cameras_button.setEnabled(True)
        self._layout.addWidget(self._apply_settings_to_cameras_button)

        self._parameter_tree_widget = ParameterTree(parent=self)
        self._layout.addWidget(self._parameter_tree_widget)
        self._parameter_tree_widget.addParameters(Parameter(name="No cameras connected...", value="", type="str"))

    def update_camera_config_parameter_tree(
            self,
            dictionary_of_webcam_configs: Dict[str, CameraConfig]
    ):
        logger.info("Updating camera configs in parameter tree")

        self._parameter_tree_widget.clear()

        for camera_config in dictionary_of_webcam_configs.values():
            self._parameter_tree_widget.addParameters(self._convert_camera_config_to_parameter(camera_config))

    def _convert_camera_config_to_parameter(self, camera_config: CameraConfig) -> Parameter:
        try:
            rotate_video_value = rotate_cv2_code_to_str(
                camera_config.rotate_video_cv2_code
            )
        except KeyError:
            rotate_video_value = "None"

        return Parameter.create(
            name="Camera_" + str(camera_config.camera_id),
            type="group",
            children=[
                Parameter(
                    name="Use this camera?",
                    type="bool",
                    value=True
                ),
                Parameter(
                    name="Rotate Image",
                    type="list",
                    limits=["None", "90_clockwise", "90_counterclockwise", "180"],
                    value=rotate_video_value,
                ),
                Parameter(
                    name="Exposure",
                    type="int",
                    value=camera_config.exposure
                ),
                Parameter(
                    name="Resolution Width",
                    type="int",
                    value=camera_config.resolution_width,
                ),
                Parameter(
                    name="Resolution Height",
                    type="int",
                    value=camera_config.resolution_height,
                ),
                self._create_apply_to_all_cameras_action_parameter(camera_id=camera_config.camera_id),

            ],
        )

    def _create_apply_to_all_cameras_action_parameter(self, camera_id) -> Parameter:
        button =  Parameter.create(
            name="Apply settings to all cameras",
            type="action",
        )
        button.sigActivated.connect(lambda: print("TODO - Make this button work lol"))
        return button


def rotate_image_str_to_cv2_code(rotate_str: str):
    if rotate_str == "90_clockwise":
        return cv2.ROTATE_90_CLOCKWISE
    elif rotate_str == "90_counterclockwise":
        return cv2.ROTATE_90_COUNTERCLOCKWISE
    elif rotate_str == "180":
        return cv2.ROTATE_180

    return None


def rotate_cv2_code_to_str(rotate_video_value):
    if rotate_video_value is None:
        return None
    elif rotate_video_value == cv2.ROTATE_90_CLOCKWISE:
        return "90_clockwise"
    elif rotate_video_value == cv2.ROTATE_90_COUNTERCLOCKWISE:
        return "90_counterclockwise"
    elif rotate_video_value == cv2.ROTATE_180:
        return "180"


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    qt_camera_config_parameter_tree_widget = QtCameraConfigParameterTreeWidget()
    qt_camera_config_parameter_tree_widget.update_camera_config_parameter_tree({'0': CameraConfig()})
    qt_camera_config_parameter_tree_widget.show()
    sys.exit(app.exec())
