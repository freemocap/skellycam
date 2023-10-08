# __main__.py
import logging
import multiprocessing
from multiprocessing import freeze_support

from skellycam.backend.backend_main import backend_main
from skellycam.frontend.frontend_main import frontend_main
from skellycam.utilities.setup_windows_app_id import setup_app_id_for_windows

logger = logging.getLogger(__name__)


def main():
    messages_from_frontend, messages_to_backend = multiprocessing.Pipe(duplex=False)
    messages_from_backend, messages_to_frontend = multiprocessing.Pipe(duplex=False)

    backend_process = multiprocessing.Process(target=backend_main, args=(messages_from_frontend, messages_to_frontend))
    frontend_process = multiprocessing.Process(target=frontend_main, args=(messages_from_backend, messages_to_backend))

    logger.info(f"Starting backend process...")
    backend_process.start()

    logger.info(f"Starting frontend process...")
    frontend_process.start()

    backend_process.join()
    frontend_process.join()

    logger.info(f"Exiting main...")

if __name__ == "__main__":
    logger.info(f"Running from __main__: {__name__} - {__file__}")
    freeze_support()
    setup_app_id_for_windows()
    main()
    logger.info(f"Exiting __main__, bye!")
