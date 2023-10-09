import logging
import time
from multiprocessing.connection import Connection

from skellycam.data_models.message_from_backend import MessageFromBackend

logger = logging.getLogger(__name__)


def backend_main(messages_from_frontend: Connection,
                 messages_to_frontend: Connection):
    logger.success(f"Backend main started!")
    while True:
        try:
            time.sleep(.001)
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
