import logging
from enum import Enum


class LogLevel(Enum):
    TRACE = 5
    DEBUG = logging.DEBUG  # 10
    INFO = logging.INFO  # 20
    SUCCESS = logging.INFO + 2 # 22
    IMPORTANT = logging.INFO + 5 # 25
    WARNING = logging.WARNING  # 30
    ERROR = logging.ERROR  # 40
    CRITICAL = logging.CRITICAL  # 50
