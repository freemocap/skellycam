import logging
import multiprocessing
import os
import threading
import time

from skellycam.api.server.server_manager import UvicornServerManager
from skellycam.api.server.server_singleton import create_server_manager

logger = logging.getLogger(__name__)


def run_server(global_kill_flag: multiprocessing.Value):
    server_manager: UvicornServerManager = create_server_manager(global_kill_flag=global_kill_flag)
    try:
        server_manager.run_server()
    except Exception as e:
        logger.error(f"Server main process ended with error: {e}")
        raise
    finally:
        global_kill_flag.value = True
        server_manager.shutdown_server()

    logger.info("Server main process ended")


def shutdown_listener_loop(global_kill_flag: multiprocessing.Value):
    while not global_kill_flag.value:
        time.sleep(1)
        if os.getenv('SKELLYCAM_SHUTDOWN'):
            logger.info("Detected SKELLYCAM_SHUTDOWN environment variable - shutting down server")
            global_kill_flag.value = True

    logger.info("Shutdown listener loop ended")


if __name__ == "__main__":
    outer_global_kill_flag = multiprocessing.Value("b", False)
    run_server(outer_global_kill_flag)
    outer_global_kill_flag.value = True
    shutdown_listener_thread = threading.Thread(target=shutdown_listener_loop, args=(outer_global_kill_flag,),
                                                daemon=True)
    shutdown_listener_thread.start()
    logger.info("Server main process ended - Thank you for using SkellyCam 💀📸✨")
    print("Done!")
