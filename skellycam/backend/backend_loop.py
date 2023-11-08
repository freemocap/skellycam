import multiprocessing
import time
import traceback

from skellycam import logger
from skellycam.backend.controller.controller import get_or_create_controller
from skellycam.backend.controller.interactions.base_models import ErrorResponse


def backend_loop(exit_event: multiprocessing.Event,
                 messages_from_backend: multiprocessing.Queue,
                 messages_from_frontend: multiprocessing.Queue,
                 frontend_frame_pipe_sender  # multiprocessing.connection.Connection
                 ) -> None:
    logger.info(f"Backend main loop starting...")
    controller = get_or_create_controller(frontend_frame_pipe_sender=frontend_frame_pipe_sender)
    try:
        while True:
            if exit_event.is_set():
                logger.info(f"Exit or reboot event set, exiting...")
                break
            time.sleep(1.0)

            if not messages_from_frontend.empty():
                message = messages_from_frontend.get()

                logger.info(
                    f"backend_main received message from frontend:\n {message}\n"
                    f"Queue size: {messages_from_frontend.qsize()}")

                response = controller.handle_interaction(interaction=message)
                logger.debug(f"backend_main sending response to frontend: {response}")
                messages_from_backend.put(response)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        logger.exception(e)
        messages_from_backend.put(ErrorResponse(success=False,
                                                data={"error": str(e),
                                                      "traceback": traceback.format_exc()}))
