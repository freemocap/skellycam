# __main__.py
import multiprocessing
from multiprocessing import freeze_support

from skellycam.api.run_backend_server import run_backend_api_server
from skellycam.frontend.run_frontend import run_frontend
from skellycam.backend.system.environment.configure_logging import configure_logging, LogLevel

configure_logging(LogLevel.TRACE)

from skellycam.backend.system.environment.get_logger import logger
from skellycam.utilities.setup_windows_app_id import setup_app_id_for_windows

if __name__ == "__main__":
    logger.info(f"Running from __main__: {__name__} - {__file__}")

    freeze_support()
    setup_app_id_for_windows()

    server_process = run_backend_api_server()

    exit_code = run_frontend()

    logger.info(f"Frontend ended with exit code: {exit_code}")

    logger.info(f"Shutting down backend/server process")
    server_process.terminate()

    print("\n--------------------------------------------------")
    print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
    print("--------------------------------------------------\n")
