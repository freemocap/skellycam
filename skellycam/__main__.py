# __main__.py
from multiprocessing import freeze_support

from skellycam.system.environment.get_logger import logger
from skellycam._main.main import main
from skellycam.utilities.setup_windows_app_id import setup_app_id_for_windows

if __name__ == "__main__":
    logger.info(f"Running from __main__: {__name__} - {__file__}")
    freeze_support()
    setup_app_id_for_windows()
    main()
    logger.info(f"Exiting __main__, bye!")

    print("\n--------------------------------------------------")
    print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
    print("--------------------------------------------------\n")
