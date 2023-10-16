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

    @property
    def welcome_view(self):
        return self.main_window.welcome_view

    @property
    def camera_grid_view(self):
        return self.main_window.camera_grid_view

    @property
    def camera_settings_view(self):
        return self.main_window.camera_settings_view

    @property
    def record_buttons_view(self):
        return self.main_window.record_buttons_view

    @property
    def interact_with_backend(self):
        return self.main_window.interact_with_backend

    def handle_backend_response(self, response: BaseResponse) -> None:
        logger.trace(f"Updating view with message type: {response}")

        if isinstance(response, CamerasDetectedResponse):
            self.camera_settings_view.update_avalable_cameras(
                available_cameras=CamerasDetectedResponse(**response.dict()).available_cameras)

    def connect_signals(self) -> None:
        self.welcome_view.start_session_button.clicked.connect(self._connect_start_session_signal)
        self.camera_settings_view.camera_configs_changed.connect(lambda: NotImplementedError())

    def _connect_start_session_signal(self):
        self.welcome_view.hide()
        self.camera_grid_view.show()
        self.record_buttons_view.show()
        self.interact_with_backend.emit(DetectCamerasInteraction.as_request())
