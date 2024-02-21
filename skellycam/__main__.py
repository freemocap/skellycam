# __main__.py
from multiprocessing import freeze_support

from skellycam._main_loop import main_loop
from skellycam.system.logging_configuration.configure_logging import (
    configure_logging,
)
from skellycam.system.logging_configuration.log_level_enum import LogLevel
from skellycam.utilities.setup_windows_app_id import setup_app_id_for_windows

configure_logging(LogLevel.DEBUG)
import logging

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info(f"Running from __main__: {__name__} - {__file__}")

    freeze_support()
    setup_app_id_for_windows()

    main_loop()

    print("\n--------------------------------------------------")
    print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
    print("--------------------------------------------------\n")

    logger.success("Done!")
