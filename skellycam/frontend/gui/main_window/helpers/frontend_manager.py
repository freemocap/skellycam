from typing import TYPE_CHECKING, Dict

from skellycam import logger
from skellycam.backend.controller.commands.interactions import BaseResponse, CamerasDetectedResponse, \
    DetectCamerasInteraction, ConnectToCamerasInteraction, CloseCamerasInteraction, UpdateCameraConfigsInteraction, \
    UpdateCameraConfigsResponse
from skellycam.data_models.cameras.camera_config import CameraConfig

if TYPE_CHECKING:
    from skellycam.frontend.gui.main_window.main_window import MainWindow
    from skellycam.frontend.gui.widgets.camera_control_panel import CameraControlPanel
    from skellycam.frontend.gui.widgets.cameras.camera_grid import CameraGrid
    from skellycam.frontend.gui.widgets.camera_parameter_tree import CameraParameterTree
    from skellycam.frontend.gui.widgets.record_buttons_view import RecordButtons
    from skellycam.frontend.gui.widgets.welcome_view import Welcome


class FrontendManager:
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window
        self.connect_signals()

    @property
    def welcome(self) -> 'Welcome':
        return self.main_window.welcome

    @property
    def camera_grid(self) -> 'CameraGrid':
        return self.main_window.camera_grid

    @property
    def record_buttons(self) -> 'RecordButtons':
        return self.main_window.record_buttons

    @property
    def camera_parameter_tree(self) -> 'CameraParameterTree':
        return self.main_window.camera_parameter_tree

    @property
    def camera_control_panel(self) -> 'CameraControlPanel':
        return self.main_window.camera_control_panel

    @property
    def camera_configs(self) -> Dict[str, CameraConfig]:
        return self.camera_parameter_tree.camera_configs

    def handle_backend_response(self, response: BaseResponse) -> None:
        logger.trace(f"Updating view with message type: {response}")

        if isinstance(response, CamerasDetectedResponse):
            self._handle_cameras_detected_response(response)
        elif isinstance(response, BaseResponse):
            logger.warning(f"Received BaseResponse with no 'response' behavior: {response}")
        else:
            raise ValueError(f"Unhandled response type: {response}")

    def _handle_cameras_detected_response(self, response):
        self.camera_parameter_tree.update_available_cameras(
            available_cameras=CamerasDetectedResponse(**response.dict()).available_cameras)
        self.camera_grid.update_camera_grid(camera_configs=self.camera_configs)

    def connect_signals(self) -> None:
        self.welcome.start_session_button.clicked.connect(self._connect_start_session_signal)

        self.camera_parameter_tree.camera_configs_changed.connect(
            self._handle_camera_configs_changed)

        self.camera_control_panel.close_cameras_button.clicked.connect(
            self.emit_close_cameras_interaction)

        self.main_window.camera_control_panel.connect_to_cameras_button.clicked.connect(
            self.emit_connect_to_cameras_interaction)

        self.main_window.camera_control_panel.detect_available_cameras_button.clicked.connect(
            self.emit_detect_cameras_interaction)

    def _connect_start_session_signal(self):
        self.main_window.welcome.hide()
        self.main_window.camera_grid.show()
        self.main_window.record_buttons.show()
        self.main_window.camera_settings_dock.show()
        self.emit_detect_cameras_interaction()

    def emit_detect_cameras_interaction(self):
        logger.info("Emitting detect cameras interaction")
        self.main_window.interact_with_backend.emit(DetectCamerasInteraction.as_request())

    def _handle_camera_configs_changed(self, camera_configs: Dict[str, CameraConfig]):
        logger.info("Handling Camera Configs Changed signal")
        self.camera_grid.update_camera_grid(camera_configs=camera_configs)
        self.main_window.interact_with_backend.emit(UpdateCameraConfigsInteraction.as_request(camera_configs=self.camera_configs))

    def emit_close_cameras_interaction(self):
        logger.info("Emitting close cameras interaction")
        self.main_window.interact_with_backend.emit(CloseCamerasInteraction.as_request())

    def emit_connect_to_cameras_interaction(self):
        logger.info("Emitting connect to cameras interaction")
        self.main_window.interact_with_backend.emit(
            ConnectToCamerasInteraction.as_request(camera_configs=self.camera_configs))
