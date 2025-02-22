import asyncio
import logging
import multiprocessing
import os
import signal
import sys
import threading

from skellycam import LOG_LEVEL
from skellycam.api.server.server_manager import UvicornServerManager
from skellycam.api.server.server_singleton import create_server_manager
from skellycam.system.logging_configuration.log_levels import LogLevels
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


async def main(global_kill_flag: multiprocessing.Value):
    active_elements_check_loop_task: asyncio.Task|None = None
    if LOG_LEVEL.value < LogLevels.DEBUG.value:
        active_elements_check_loop_task = asyncio.create_task(
            active_elements_check_loop(global_kill_flag=global_kill_flag,

                                       context="Skellycam Server"
                                       ),
            name="AppLifecycleCheckLoop")
        active_elements_check_loop_task.add_done_callback(lambda _: logger.info("Shutdown listener loop task ended"))

    main_server_thread = threading.Thread(target=run_server,
                                          kwargs=dict(global_kill_flag=global_kill_flag),
                                          name="MainServerThread")
    main_server_thread.start()

    if active_elements_check_loop_task:
        await asyncio.gather(active_elements_check_loop_task, return_exceptions=True)
    logger.debug("joining main server thread...")
    main_server_thread.join()
    logger.debug("Main server thread complete - exiting main function")
    global_kill_flag.value = True


def handle_shutdown_signal(signum, frame):
    """Signal handler for termination signals."""
    logger.info(f"Received shutdown signal {signum} - setting global kill flag to True")
    original_global_kill_flag.value = True


if __name__ == "__main__":
    original_global_kill_flag = multiprocessing.Value("b", False)

    # Register signal handlers - these will set the global kill flag to True when the process receives a termination signal
    signal.signal(signal.SIGTERM, handle_shutdown_signal)  # Normal termination signal
    signal.signal(signal.SIGINT, handle_shutdown_signal)  # Ctrl+C

    try:
        asyncio.run(main(global_kill_flag=original_global_kill_flag))
    finally:
        original_global_kill_flag.value = True  # Ensure cleanup

    print("Done!  Thank you for using SkellyCam 💀📸✨")
    os.kill(os.getpid(), signal.SIGTERM)
    print("shouldn't see this")
    sys.exit(0)
