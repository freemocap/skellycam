import logging

from skellycam.backend.system.environment.logging_configuration.log_level_enum import (
    LogLevel,
)
from skellycam.backend.system.environment.logging_configuration.log_test_messages import (
    log_test_messages,
)
from skellycam.backend.system.environment.logging_configuration.logger_builder import (
    LoggerBuilder,
)

# Suppress some annoying log messages
logging.getLogger("tzlocal").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING)

logging.addLevelName(LogLevel.TRACE.value, "TRACE")
logging.addLevelName(LogLevel.SUCCESS.value, "SUCCESS")


def configure_logging(level: LogLevel = LogLevel.INFO):
    def trace(self, message, *args, **kws):
        if self.isEnabledFor(LogLevel.TRACE.value):
            self._log(LogLevel.TRACE.value, message, args, **kws, stacklevel=2)

    logging.Logger.trace = trace

    def success(self, message, *args, **kws):
        if self.isEnabledFor(LogLevel.SUCCESS.value):
            self._log(LogLevel.SUCCESS.value, message, args, **kws, stacklevel=2)

    logging.Logger.success = success

    builder = LoggerBuilder(level)
    builder.configure()


if __name__ == "__main__":
    import logging

    logger = logging.getLogger(__name__)

    configure_logging(LogLevel.TRACE)  # Setting the root logger level to TRACE
    log_test_messages(logger)
    logger.success(
        "Logging setup and tests completed. Check the console output and the log file."
    )
