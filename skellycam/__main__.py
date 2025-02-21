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


async def main(global_kill_flag: multiprocessing.Value):
    active_elements_check_loop_task = asyncio.create_task(active_elements_check_loop(global_kill_flag=global_kill_flag,

                                                                                     context="Skellycam Server"
                                                                                     ),
                                                          name="AppLifecycleCheckLoop")
    active_elements_check_loop_task.add_done_callback(lambda _: logger.info("Shutdown listener loop task ended"))

    main_server_thread = threading.Thread(target=run_server,
                                          kwargs=dict(global_kill_flag=global_kill_flag),
                                          name="MainServerThread")
    main_server_thread.start()

    await asyncio.gather(active_elements_check_loop_task, return_exceptions=True)
    logger.debug("joining main server thread...")
    main_server_thread.join()
    logger.debug("Main server thread complete - exiting main function")
    global_kill_flag.value = True


# def set_shutdown_flag_after_10s():
#     # Wait for 10 seconds
#     for _ in range(10):
#         time.sleep(1)
#         print(f"os.getenv('SKELLYCAM_SHOULD_SHUTDOWN'): {os.getenv('SKELLYCAM_SHOULD_SHUTDOWN')}")
#     # Set the environment variable
#     os.environ["SKELLYCAM_SHOULD_SHUTDOWN"] = "True"
#     print("Environment variable set to:", os.getenv("SKELLYCAM_SHOULD_SHUTDOWN"))
#
#
# # Create and start the thread
# shutdown_thread = threading.Thread(target=set_shutdown_flag_after_10s, name="ShutdownThread")
# shutdown_thread.start()


def check_shutdown_flag(global_kill_flag: multiprocessing.Value):
    while not global_kill_flag.value:
        time.sleep(1)
        if os.getenv("SKELLYCAM_SHOULD_SHUTDOWN"):
            global_kill_flag.value = True
            logger.info("Shutdown environment flag detected - setting global kill flag to True")
            break


if __name__ == "__main__":
    original_global_kill_flag = multiprocessing.Value("b", False)
    check_shutdown_flag_thread = threading.Thread(target=check_shutdown_flag,
                                                  args=(original_global_kill_flag,),
                                                  daemon=True,
                                                  name="CheckShutdownFlagThread")
    check_shutdown_flag_thread.start()
    asyncio.run(main(global_kill_flag=original_global_kill_flag))
    print("Done!  Thank you for using SkellyCam 💀📸✨")
    os.kill(os.getpid(), signal.SIGTERM)
    sys.exit(0)
