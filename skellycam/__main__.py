# __main__.py
import logging
import multiprocessing
import sys

from skellycam.api.run_server import run_uvicorn_server
from skellycam.system.utilities.setup_windows_app_id import setup_app_id_for_windows

logger = logging.getLogger(__name__)

HOSTNAME = "localhost"
PORT = 8003
APP_URL = f"http://{HOSTNAME}:{PORT}"

if __name__ == "__main__":

    multiprocessing.freeze_support()
    # multiprocessing.set_start_method("fork") # might be needed for MacOS or Linux?

    print(f"Running from __main__: {__name__} - {__file__} [print via `print(...)`]")
    logger.info(f"Running from __main__: {__name__} - {__file__} [log via `logger.info(...)`]")

    if sys.platform == "win32":
        setup_app_id_for_windows()

    run_uvicorn_server(HOSTNAME, PORT)

    print("\n\n--------------------------------------------------\n--------------------------------------------------")
    print("Thank you for using SkellyCam \U0001F480 \U0001F4F8 \U00002728 \U0001F495")
    print("--------------------------------------------------\n--------------------------------------------------\n\n")

    logger.success("Done!")
