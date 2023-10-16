import multiprocessing
import pprint
import time
import traceback

from skellycam import logger
from skellycam.backend.controller.commands.requests_commands import ErrorResponse
from skellycam.backend.controller.controller import get_or_create_controller


def backend_loop(exit_event: multiprocessing.Event,
                 messages_from_backend: multiprocessing.Queue,
                 messages_from_frontend: multiprocessing.Queue):
    logger.info(f"Backend main loop starting...")
    controller = get_or_create_controller()

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

                response = controller.handle_message(message=message)
                messages_from_backend.put(response)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        logger.exception(e)
        messages_from_backend.put(ErrorResponse(success=False,
                                           data={"error": str(e),
                                                 "traceback": traceback.format_exc()}))
