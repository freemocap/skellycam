import multiprocessing
import pprint
import time
from multiprocessing import Event

from skellycam import logger
from skellycam.data_models.message_from_backend import MessageFromBackend


def backend_main_loop(messages_from_frontend: multiprocessing.Queue,
                      messages_from_backend: multiprocessing.Queue,
                      exit_event: Event):
    logger.success(f"Backend main started!")
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
            print("An error occurred: ", str(e))
            messages_from_backend.put(MessageFromBackend(type="error",
                                                        message=str(e),
                                                        data={}))
