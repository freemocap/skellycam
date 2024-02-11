import logging

from skellycam.backend.system.environment.configure_logging import (
    configure_logging,
    LogLevel,
)

configure_logging(LogLevel.DEBUG)
logger = logging.getLogger(__name__)
