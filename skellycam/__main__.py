# __main__.py
from multiprocessing import freeze_support

from skellycam._main_loop import main_loop
from skellycam.system.logging_configuration.configure_logging import (
    configure_logging,
)
from skellycam import LogLevel
from skellycam.utilities.setup_windows_app_id import setup_app_id_for_windows

configure_logging(LogLevel.DEBUG)
import logging

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    freeze_support()
    print(f"Running from __main__: {__name__} - {__file__}")
    logger.info(f"Running from __main__: {__name__} - {__file__}")

    setup_app_id_for_windows()
    main_loop()

    print("\n--------------------------------------------------")
    print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
    print("--------------------------------------------------\n")

    logger.success("Done!")
