import logging
import sys
from logging.config import dictConfig

from skellycam.system.default_paths import get_log_file_path
from skellycam.system.logging_configuration.custom_formatter import (
    CustomFormatter,
)
from skellycam.system.logging_configuration.delta_time_filter import (
    DeltaTimeFilter,
)
from skellycam.system.logging_configuration.log_level_enum import (
    LogLevels,
)
from skellycam.system.logging_configuration.logging_color_helpers import (
    get_hashed_color,
)


class LoggerBuilder:
    DEFAULT_LOGGING = {"version": 1, "disable_existing_loggers": False}
    # https://www.alt-codes.net/editor.php
    format_string = (
        "┌──────────────────────────────────────────────────────────────────────┤ %(levelname)s |  %(name)s.%(funcName)s():%(lineno)s | %(delta_t)s | %(asctime)s | PID:%(process)d:%(processName)s TID:%(thread)d:%(threadName)s \n%(message)s"
    )

    def __init__(self, level: LogLevels):
        self.default_logging_formatter = CustomFormatter(
            fmt=self.format_string, datefmt="%Y-%m-%dT%H:%M:%S"
        )
        dictConfig(self.DEFAULT_LOGGING)

        self._set_logging_level(level)

    def _set_logging_level(self, level: LogLevels):
        logging.root.setLevel(level.value)

    def build_file_handler(self):
        file_handler = logging.FileHandler(get_log_file_path(), encoding="utf-8")
        file_handler.setLevel(LogLevels.TRACE.value)
        file_handler.setFormatter(self.default_logging_formatter)
        file_handler.addFilter(DeltaTimeFilter())
        return file_handler

    class ColoredConsoleHandler(logging.StreamHandler):

        COLORS = {
            # Define color codes for different log levels with ANSI escape codes
            # https://en.wikipedia.org/wiki/ANSI_escape_code
            "LOOP": "\033[90m",  # Bright Black (grey)
            "TRACE": "\033[37m",  # Dark White (also grey lol)
            "DEBUG": "\033[34m",  # Blue
            "INFO": "\033[96m",  # Cyan
            "SUCCESS": "\033[95m",  # Magenta
            "API": "\033[92m",  # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[30m\033[41m",  # Black text on Red background
        }

        def emit(self, record):
            """
            Overrides the emit method to colorize logs according to the level when
            outputting to the console.
            """
            # Apply color to indicate the process ID (PID) first
            pid_color = get_hashed_color(record.process)
            record.process_colored = pid_color + f"PID:{record.process}:{record.processName}" + "\033[0m"

            # Then apply color to indicate the thread ID (TID)
            tid_color = get_hashed_color(record.thread)
            record.thread_colored = tid_color + f"TID:{record.thread}:{record.threadName}" + "\033[0m"

            # Use the CustomFormatter to format the record
            formatted_record = self.format(record)

            # Apply color code to the formatted record except PID and TID
            color_code = self.COLORS.get(record.levelname, "\033[0m")
            formatted_record = (
                formatted_record
                .replace(f"PID:{record.process}:{record.processName}", record.process_colored)
                .replace(f"TID:{record.thread}:{record.threadName}", record.thread_colored)
            )

            formatted_record = formatted_record.replace(record.getMessage(),
                                                        color_code + "└» " + self.word_wrap(record.getMessage()) + "\033[0m")
            formatted_record = color_code + formatted_record + "\033[0m"
            # Output the final colorized and formatted record to the console
            print(formatted_record)

        def word_wrap(self, text, width=200, look_for_breaks_withing: int = 10):
            """
            Wraps text to a specified width, preserving whole words if there is a break within the specified number of characters from the end of the line.
            """
            if len(text) <= width:
                return text

            lines = []
            while len(text) > width:
                # Find the last space within the look_for_breaks_withing characters from the end of the line
                last_space = text.rfind(" ", 0, width - look_for_breaks_withing)
                if last_space == -1:
                    # If there is no space within the specified range, just break at the width
                    last_space = width

                log_line = text[:last_space].strip()
                if len(lines) > 0:
                    log_line = "\t" + log_line
                lines.append(log_line)
                text = text[last_space:].strip()
            lines.append(f"\t{text}") if len(text) > 0 else None
            return "\n".join(lines)

    def build_console_handler(self):
        console_handler = self.ColoredConsoleHandler(stream=sys.stdout)
        console_handler.setLevel(LogLevels.LOOP.value)
        console_handler.setFormatter(self.default_logging_formatter)
        console_handler.addFilter(DeltaTimeFilter())
        return console_handler

    def configure(self):
        if len(logging.getLogger().handlers) == 0:
            handlers = [self.build_file_handler(), self.build_console_handler()]
            for handler in handlers:
                if handler not in logging.getLogger("").handlers:
                    logging.getLogger("").handlers.append(handler)
        else:
            logger = logging.getLogger(__name__)
            logger.trace("Logging already configured")
