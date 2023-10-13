from typing import TYPE_CHECKING

from skellycam import logger
from skellycam.data_models.request_response_update import UpdateModel, MessageType, Request, EventTypes, BaseMessage

if TYPE_CHECKING:
    from skellycam.frontend.gui.main_window.main_window import MainWindow


class ViewUpdater:
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window

    def handle_message(self, message: BaseMessage) -> None:
        logger.trace(f"Updating view with message type: {message.message_type}")
        if message.message_type == MessageType.ERROR:
            logger.error(f"Backend sent error message: {message.data['error']}!")
            return

        match message.event:
            case EventTypes.SESSION_STARTED:
                logger.debug(f"Heard `session_started` event, updating view...")
                self.main_window.camera_grid.show()
                self.main_window.control_panel.show()
                self.main_window.welcome.hide()
            case EventTypes.CAMERA_DETECTED:
                logger.debug(f"Heard `camera_detected` event, updating view...")
                self.main_window.camera_grid.update_view(message)


