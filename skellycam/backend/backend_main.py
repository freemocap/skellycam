import multiprocessing
import pprint
import time
import traceback
from multiprocessing import Event

from skellycam import logger
from skellycam.backend.controller.controller import get_or_create_controller
from skellycam.data_models.request_response_update import Response, MessageType, Request, EventTypes

CONTROLLER = None


def backend_main(messages_from_frontend: multiprocessing.Queue,
                 messages_from_backend: multiprocessing.Queue,
                 exit_event: Event):
    logger.success(f"Backend main started!")
    backend_loop(exit_event=exit_event,
                 messages_from_backend=messages_from_backend,
                 messages_from_frontend=messages_from_frontend)

    if not exit_event.is_set():
        logger.info(f"SETTING EXIT EVENT")
        exit_event.set()


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
                request = Request(**messages_from_frontend.get())

                logger.info(
                    f"backend_main received message from frontend:\n {pprint.pformat(request.dict(), indent=4)}\n"
                    f"Queue size: {messages_from_frontend.qsize()}")
                response = controller.handle_request(request=request)
                messages_from_backend.put(response)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        logger.exception(e)
        messages_from_backend.put(Response(message_type=MessageType.ERROR,
                                           success=False,
                                           data={"error": str(e),
                                                 "traceback": traceback.format_exc()}))
