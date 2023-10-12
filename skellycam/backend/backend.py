import multiprocessing
import pprint
import time
from multiprocessing import Event

from skellycam import logger
from skellycam.backend.controller.controller import get_or_create_controller

CONTROLLER = None


def backend_main_loop(messages_from_frontend: multiprocessing.Queue,
                      messages_from_backend: multiprocessing.Queue,
                      exit_event: Event):
    logger.success(f"Backend main started!")
    controller = get_or_create_controller()
    while True:
        # logger.trace(f"Checking for messages from frontend...")
        try:
            if exit_event.is_set():
                logger.info(f"Exit or reboot event set, exiting...")
                break
            time.sleep(1.0)
            if not messages_from_frontend.empty():
                message = messages_from_frontend.get()
                logger.info(f"Backend received message from frontend: queue size: {messages_from_frontend.qsize()}")
                logger.info(f"backend_main received message from frontend:\n {pprint.pformat(message, indent=4)}")

                messages_from_backend.put(MessageFromBackend(type="success",
                                                             message="Backend received message",
                                                             data={"wow": "cool data"}))
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            messages_from_backend.put(MessageFromBackend(type="error",
                                                         message=str(e),
                                                         data={e.with_traceback()}))
            raise e
        finally:
            if not exit_event.is_set():
                logger.info(f"Exiting backend main loop ...")
                exit_event.set()
