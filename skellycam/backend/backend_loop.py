import multiprocessing
import time
import traceback

from skellycam.system.environment.get_logger import logger
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
        backend_main_runner(controller, exit_event, messages_from_backend, messages_from_frontend)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        logger.exception(e)
        messages_from_backend.put(ErrorResponse(success=False,
                                                data={"error": str(e),
                                                      "traceback": traceback.format_exc()}))


def backend_main_runner(controller,
                        exit_event,
                        messages_from_backend, messages_from_frontend):
    while True:
        if exit_event.is_set():
            logger.info(f"Exit or reboot event set, exiting...")
            break
        time.sleep(1.0)

        if not messages_from_frontend.empty():
            message = messages_from_frontend.get()

            logger.info(f"Backend_main received message from frontend:\n {message}\n")

            response = controller.handle_interaction(interaction=message)
            logger.debug(f"backend_main sending response to frontend: {response}")
            messages_from_backend.put(response)
