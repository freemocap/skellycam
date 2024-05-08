import logging

import pytest

from skellycam.system.logging_configuration.configure_logging import configure_logging
from skellycam.system.logging_configuration.log_level_enum import LogLevels


@pytest.fixture
def test_logger():
    configure_logging(LogLevels.LOOP)
    logger = logging.getLogger(__name__)
    return logger


def test_logging_something(test_logger):
    test_logger.loop("This is a test loop message")
    assert True

    test_logger.trace("This is a test trace message")
    assert True

    test_logger.debug("This is a test debug message")
    assert True

    test_logger.info("This is a test info message")
    assert True

    test_logger.success("This is a test success message")
    assert True

    test_logger.api("This is a test api message")
    assert True

    test_logger.warning("This is a test warning message")
    assert True

    test_logger.success("This is a test success message")
    assert True

    test_logger.error("This is a test error message")
    assert True

    test_logger.critical("This is a test critical message")
    assert True
