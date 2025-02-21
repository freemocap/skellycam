import asyncio
import logging
import multiprocessing
import os
import signal
import sys
import threading
import time

from skellycam.api.server.server_manager import UvicornServerManager
from skellycam.api.server.server_singleton import create_server_manager
from skellycam.utilities.active_elements_check import active_elements_check_loop

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


async def main():
    original_global_kill_flag = multiprocessing.Value("b", False)
    active_elements_check_loop_task = asyncio.create_task(active_elements_check_loop(global_kill_flag=original_global_kill_flag,

                                                                                     context="Skellycam Server"
                                                                                     ),
                                                          name="AppLifecycleCheckLoop")
    active_elements_check_loop_task.add_done_callback(lambda _: logger.info("Shutdown listener loop task ended"))

    main_server_thread = threading.Thread(target=run_server,
                                          kwargs=dict(global_kill_flag=original_global_kill_flag),
                                          name="MainServerThread")
    main_server_thread.start()

    await asyncio.gather(active_elements_check_loop_task, return_exceptions=True)
    logger.debug("joining main server thread...")
    main_server_thread.join()
    logger.debug("Main server thread complete - exiting main function")
    original_global_kill_flag.value = True


if __name__ == "__main__":
    asyncio.run(main())
    print("Done!  Thank you for using SkellyCam 💀📸✨")
    os.kill(os.getpid(), signal.SIGTERM)
    sys.exit(0)