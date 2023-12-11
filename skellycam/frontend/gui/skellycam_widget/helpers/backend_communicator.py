import multiprocessing
from typing import Callable

from PySide6.QtCore import QTimer

from skellycam.system.environment.get_logger import logger
from skellycam.backend.controller.interactions.base_models import BaseResponse, BaseInteraction


class BackendCommunicator:
    def __init__(self,
                 messages_from_frontend: multiprocessing.Queue,
                 messages_from_backend: multiprocessing.Queue,
                 frontend_frame_pipe_receiver,  # multiprocessing.connection.Connection,
                 handle_backend_response: Callable[[BaseResponse], None],
                 parent=None,

                 ):
        self._parent = parent
        self._messages_from_frontend = messages_from_frontend
        self._messages_from_backend = messages_from_backend
        self._frontend_frame_pipe_receiver = frontend_frame_pipe_receiver
        self._handle_backend_response = handle_backend_response

    def start(self):
        self._update_timer = QTimer()
        self._update_timer.start(500)
        self._update_timer.timeout.connect(self._check_for_messages_from_backend)

    def _check_for_messages_from_backend(self):
        if not self._messages_from_backend.empty():
            response: BaseResponse = self._messages_from_backend.get()
            logger.info(f"frontend_main received message from backend: {response}")
            if not response.success:
                logger.error(f"Backend sent error message: {response}!")
            self._handle_backend_response(response)

    def send_interaction_to_backend(self, interaction: BaseInteraction) -> None:
        logger.debug(f"Sending interaction to backend: {interaction}")
        self._messages_from_frontend.put(interaction)
