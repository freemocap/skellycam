# __main__.py
import multiprocessing
from multiprocessing import freeze_support

from skellycam.api.run_server import run_backend_api_server, run_backend
from skellycam.frontend.run_frontend import run_frontend
from skellycam.backend.system.environment.configure_logging import configure_logging, LogLevel

configure_logging(LogLevel.TRACE)

from skellycam.backend.system.environment.get_logger import logger
from skellycam.utilities.setup_windows_app_id import setup_app_id_for_windows

if __name__ == "__main__":
    logger.info(f"Running from __main__: {__name__} - {__file__}")

    freeze_support()
    setup_app_id_for_windows()

    logger.info("Starting backend server...")
    backend_process, api_url = run_backend()

    exit_code = run_frontend(api_url)

    ###

    logger.info(f"Frontend ended with exit code: {exit_code}")
    logger.info(f"Shutting down backend/server process")
    backend_process.terminate()

    print("\n--------------------------------------------------")
    print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
    print("--------------------------------------------------\n")
