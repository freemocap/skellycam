import multiprocessing
import time
from typing import Callable

from PySide6.QtCore import QThread

from skellycam import logger
from skellycam.backend.controller.interactions.base_models import BaseResponse, BaseInteraction


class BackendCommunicator(QThread):
    def __init__(self,
                 messages_from_frontend: multiprocessing.Queue,
                 messages_from_backend: multiprocessing.Queue,
                 frontend_frame_pipe_receiver,  # multiprocessing.connection.Connection,
                 handle_backend_response: Callable[[BaseResponse], None],
                 parent=None,

                 ):
        super().__init__(parent=parent)
        self._parent = parent
        self._messages_from_frontend = messages_from_frontend
        self._messages_from_backend = messages_from_backend
        self._frontend_frame_pipe_receiver = frontend_frame_pipe_receiver
        self._handle_backend_response = handle_backend_response

    def run(self) -> None:
        logger.info(f"Backend Communicator loop starting...")
        loop_time = 0.5
        while True:
            time.sleep(loop_time)
            if not self._messages_from_backend.empty():
                response: BaseResponse = self._messages_from_backend.get()
                logger.info(f"frontend_main received message from backend: {response}")
                if not response.success:
                    logger.error(f"Backend sent error message: {response}!")
                self._handle_backend_response(response)

    def send_interaction_to_backend(self, interaction: BaseInteraction) -> None:
        logger.debug(f"Sending interaction to backend: {interaction}")
        self._messages_from_frontend.put(interaction)
