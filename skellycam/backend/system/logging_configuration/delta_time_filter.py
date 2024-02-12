import logging
from datetime import datetime


class DeltaTimeFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.prev_time = datetime.now().timestamp()

    def filter(self, record):
        current_time = datetime.now().timestamp()
        delta = current_time - self.prev_time
        record.delta_t = f"Δt:{delta:.6f}s"
        self.prev_time = current_time
        return True
