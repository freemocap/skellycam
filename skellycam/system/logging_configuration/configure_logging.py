import logging

from skellycam.system.logging_configuration.log_level_enum import (
    LogLevel,
)
from skellycam.system.logging_configuration.log_test_messages import (
    log_test_messages,
)
from skellycam.system.logging_configuration.logger_builder import (
    LoggerBuilder,
)

# Suppress some annoying log messages
logging.getLogger("tzlocal").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.INFO)

logging.addLevelName(LogLevel.LOOP.value, "LOOP")
logging.addLevelName(LogLevel.TRACE.value, "TRACE")
logging.addLevelName(LogLevel.SUCCESS.value, "SUCCESS")
logging.addLevelName(LogLevel.API.value, "API")


def add_log_method(level: LogLevel, name: str):
    def log_method(self, message, *args, **kws):
        if self.isEnabledFor(level.value):
            self._log(level.value, message, args, **kws, stacklevel=2)

    setattr(logging.Logger, name, log_method)


def configure_logging(level: LogLevel = LogLevel.DEBUG):
    add_log_method(LogLevel.LOOP, 'loop')
    add_log_method(LogLevel.TRACE, 'trace')
    add_log_method(LogLevel.API, 'api')
    add_log_method(LogLevel.SUCCESS, 'success')

    builder = LoggerBuilder(level)
    builder.configure()
    logger = logging.getLogger(__name__)
    logger.debug(f"Logging configured - level: {level}")


if __name__ == "__main__":
    logger_test = logging.getLogger(__name__)
    log_test_messages(logger_test)
    logger_test.success(
        "Logging setup and tests completed. Check the console output and the log file."
    )
