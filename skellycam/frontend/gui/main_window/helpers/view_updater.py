from typing import TYPE_CHECKING

from skellycam import logger
from skellycam.data_models.request_response_update import BaseMessage, CamerasDetected, DetectAvailableCameras

if TYPE_CHECKING:
    from skellycam.frontend.gui.main_window.main_window import MainWindow


class ViewUpdater:
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window
        self.connect_signals_to_slots()

    def handle_message(self, message: BaseMessage) -> None:
        logger.trace(f"Updating view with message type: {message.__class__}")

        match message.__class__:
            case CamerasDetected.__class__:
                self.main_window.camera_settings_view.update_parameter_tree(
                    available_cameras=message.data["available_camera_devices"])

    def connect_signals_to_slots(self) -> None:
        self._connect_start_session_signal()

    def _connect_start_session_signal(self):
        self.main_window.welcome_view.session_started.connect(lambda: self.main_window.camera_grid_view.show())
        self.main_window.welcome_view.session_started.connect(lambda: self.main_window.record_buttons_view.show())
        self.main_window.welcome_view.session_started.connect(
            lambda: self.main_window.emit_message(DetectAvailableCameras()))
