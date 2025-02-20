import logging
from logging import LogRecord
from queue import Queue
from ..formatters.custom_formatter import CustomFormatter
from ..filters.delta_time import DeltaTimeFilter
from ..log_format_string import LOG_FORMAT_STRING


class WebSocketQueueHandler(logging.Handler):
    """Formats logs and puts them in a queue for websocket distribution"""

    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue
        self.setFormatter(CustomFormatter(LOG_FORMAT_STRING))
        self.addFilter(DeltaTimeFilter())

    def emit(self, record: logging.LogRecord):
        log_record_dict =  record.__dict__
        log_record_dict["formatted_message"] = self.format(record) # replace ANSI codes with spans and hex colors
        self.queue.put(log_record_dict)

MAX_WEBSOCKET_LOG_QUEUE_SIZE = 1000
WEBSOCKET_LOG_QUEUE: Queue| None = None
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