import time
from multiprocessing import Event
from multiprocessing.connection import Connection

from skellycam import logger
from skellycam.data_models.message_from_backend import MessageFromBackend


def backend_main(messages_from_frontend: Connection,
                 messages_to_frontend: Connection,
                 exit_event: Event):
    logger.success(f"Backend main started!")
    while True:
        logger.trace(f"Checking for messages from frontend...")
        try:
            if exit_event.is_set():
                logger.info(f"Exit or reboot event set, exiting...")
                break
            time.sleep(1.0)
            if messages_from_frontend.poll():
                message = messages_from_frontend.recv()
                logger.info(f"backend_main received message from frontend: {message}")
                messages_to_frontend.send(MessageFromBackend(type="success",
                                                             message="Backend received message",
                                                             data={"wow": "cool data"}))
        except Exception as e:
            print("An error occurred: ", str(e))
            messages_to_frontend.send(MessageFromBackend(type="error",
                                                         message=str(e),
                                                         data={}))
