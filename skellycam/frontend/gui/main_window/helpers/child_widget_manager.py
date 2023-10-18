from typing import TYPE_CHECKING

from skellycam import logger
from skellycam.backend.controller.commands.requests_commands import BaseResponse, CamerasDetectedResponse, \
    DetectCamerasInteraction

if TYPE_CHECKING:
    from skellycam.frontend.gui.main_window.main_window import MainWindow


class ChildWidgetManager:
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window
        self.connect_signals()

    def handle_backend_response(self, response: BaseResponse) -> None:
        logger.trace(f"Updating view with message type: {response}")

        if isinstance(response, CamerasDetectedResponse):
            self.main_window.camera_parameter_tree.update_avalable_cameras(
                available_cameras=CamerasDetectedResponse(**response.dict()).available_cameras)

    def connect_signals(self) -> None:
        self.main_window.welcome_view.start_session_button.clicked.connect(self._connect_start_session_signal)
        self.main_window.camera_parameter_tree.camera_configs_changed.connect(
            self.emit_update_camera_configs_interaction)
        self.main_window.camera_control_panel.close_cameras_button.clicked.connect(
            lambda: logger.info("Closing cameras..."))
        self.main_window.camera_control_panel.connect_to_cameras_button.clicked.connect(
            lambda: logger.info("Connecting to cameras..."))
        self.main_window.camera_control_panel.detect_available_cameras_button.clicked.connect(
            self.emit_detect_cameras_interaction)

    def _connect_start_session_signal(self):
        self.main_window.welcome_view.hide()
        self.main_window.camera_grid_view.show()
        self.main_window.record_buttons_view.show()
        self.main_window.camera_settings_dock.show()
        self.emit_detect_cameras_interaction()

    def emit_detect_cameras_interaction(self):
        logger.info("Emitting detect cameras interaction")
        self.main_window.interact_with_backend.emit(DetectCamerasInteraction.as_request())

    def emit_update_camera_configs_interaction(self):
        logger.info("Emitting update camera configs interaction")
        # self.main_window.interact_with_backend.emit(UpdateCameraConfigsInteraction.as_request(camera_configs=self.main_window.camera_parameter_tree.camera_configs))

    def emit_close_cameras_interaction(self):
        logger.info("Emitting close cameras interaction")
        # self.main_window.interact_with_backend.emit(CloseCamerasInteraction.as_request())

    def emit_connect_to_cameras_interaction(self):
        logger.info("Emitting connect to cameras interaction")
        # self.main_window.interact_with_backend.emit(ConnectToCamerasInteraction.as_request())
