from typing import TYPE_CHECKING

from skellycam import logger
from skellycam.data_models.request_response_update import UpdateModel
if TYPE_CHECKING:
    from skellycam.frontend.gui.main_window.main_window import MainWindow


def update_view(main_window: 'MainWindow', update: UpdateModel):
    match update.data["event"]:
        case "session_started":
            logger.debug(f"Heard `session_started` event, updating view...")
            main_window.camera_grid.show()
            main_window.control_panel.show()
            main_window.welcome.hide()


