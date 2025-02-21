import logging
import multiprocessing
from multiprocessing import Queue
from typing import Optional

from ..formatters.custom_formatter import CustomFormatter
from ..filters.delta_time import DeltaTimeFilter
from ..log_format_string import LOG_FORMAT_STRING
from pydantic import BaseModel

class LogRecordModel(BaseModel):
    name: str
    msg: str
    args: list
    levelname: str
    levelno: int
    pathname: str
    filename: str
    module: str
    exc_info: str|None
    exc_text: str|None
    stack_info: str|None
    lineno: int
    funcName: str
    created: float
    msecs: float
    relativeCreated: float
    thread: int
    threadName: str
    processName: str
    process: int
    delta_t: str
    message: str
    asctime: str
    formatted_message: str
    type: str

class WebSocketQueueHandler(logging.Handler):
    """Formats logs and puts them in a queue for websocket distribution"""

    def __init__(self, queue: multiprocessing.Queue):
        super().__init__()
        self.queue = queue
        self.addFilter(DeltaTimeFilter())
        self.setFormatter(CustomFormatter(LOG_FORMAT_STRING))

    def emit(self, record: logging.LogRecord):
        log_record_dict =  record.__dict__
        log_record_dict["formatted_message"] = self.format(record)
        log_record_dict['type'] = record.__class__.__name__
        self.queue.put(LogRecordModel(**log_record_dict).model_dump())

MAX_WEBSOCKET_LOG_QUEUE_SIZE = 1000
WEBSOCKET_LOG_QUEUE: Optional[Queue] = None
def create_websocket_log_queue() -> Queue:
    global WEBSOCKET_LOG_QUEUE
    if WEBSOCKET_LOG_QUEUE is None:
        WEBSOCKET_LOG_QUEUE = Queue(maxsize=MAX_WEBSOCKET_LOG_QUEUE_SIZE)
    return WEBSOCKET_LOG_QUEUE

def get_websocket_log_queue() -> Queue:
    global WEBSOCKET_LOG_QUEUE
    if WEBSOCKET_LOG_QUEUE is None:
        raise ValueError("Websocket log queue not created yet")
    return WEBSOCKET_LOG_QUEUE