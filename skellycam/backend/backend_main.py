import logging
import time
from multiprocessing.connection import Connection

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MessageFromBackend(BaseModel):
    type: str = Field(default_factory=str, description="success, error, warning, etc.")
    message: str = Field(default_factory=str, description="A message to display to the user")
    data: dict = Field(default_factory=dict, description="Any data to send to the frontend")


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
