import logging

from skellycam.system.logging_configuration.log_levels import LogLevels
from skellycam.system.logging_configuration.package_log_quieters import suppress_noisy_package_logs
from .log_test_messages import log_test_messages
from .logger_builder import LoggerBuilder

suppress_noisy_package_logs()
# Add custom log levels
logging.addLevelName(LogLevels.GUI.value, "GUI")
logging.addLevelName(LogLevels.LOOP.value, "LOOP")
logging.addLevelName(LogLevels.TRACE.value, "TRACE")
logging.addLevelName(LogLevels.SUCCESS.value, "SUCCESS")
logging.addLevelName(LogLevels.API.value, "API")


def add_log_method(level: LogLevels, name: str):
    def log_method(self, message, *args, **kws):
        if self.isEnabledFor(level.value):
            self._log(level.value, message, args, **kws, stacklevel=2)

    setattr(logging.Logger, name, log_method)


def configure_logging(level: LogLevels = LogLevels.DEBUG):
    add_log_method(LogLevels.GUI, 'gui')
    add_log_method(LogLevels.LOOP, 'loop')
    add_log_method(LogLevels.TRACE, 'trace')
    add_log_method(LogLevels.API, 'api')
    add_log_method(LogLevels.SUCCESS, 'success')

    builder = LoggerBuilder(level)
    builder.configure()


if __name__ == "__main__":
    logger_test = logging.getLogger(__name__)
    log_test_messages(logger_test)
    logger_test.success(
        "Logging setup and tests completed. Check the console output and the log file."
    )
