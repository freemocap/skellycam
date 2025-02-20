import sys
import logging
from ..formatters.color_formatter import ColorFormatter
from ..filters.delta_time import DeltaTimeFilter
from ..log_format_string import LOG_FORMAT_STRING


class ColoredConsoleHandler(logging.StreamHandler):
    """Colorized console output with Δt and process/thread coloring"""

    def __init__(self, stream=sys.stdout):
        super().__init__(stream)
        self.setFormatter(ColorFormatter(LOG_FORMAT_STRING))
        self.addFilter(DeltaTimeFilter())