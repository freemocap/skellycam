import asyncio
import logging
import multiprocessing
import os
import signal

import uvicorn

from skellycam.api.server_constants import HOSTNAME, PORT
from skellycam.app import create_fastapi_app
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry
from skellycam.utilities.kill_process_on_port import kill_process_on_port
from skellycam.utilities.wait_functions import await_1s

logger = logging.getLogger(__name__)


async def main() -> None:
    global_kill_flag = multiprocessing.Value("b", False)
    process_registry = ProcessRegistry(
        global_kill_flag=global_kill_flag,
    )
    process_registry.start_heartbeat()

    server: uvicorn.Server | None = None

    def handle_signal(signum: int, frame: object) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        global_kill_flag.value = True
        if server:
            server.should_exit = True

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        kill_process_on_port(port=PORT)

        app = create_fastapi_app(
            global_kill_flag=global_kill_flag,
            process_registry=process_registry,
        )

        config = uvicorn.Config(
            app=app,
            host=HOSTNAME,
            port=PORT,
            log_level="warning",
            reload=False,
        )
        server = uvicorn.Server(config)

        logger.info(f"Starting server on {HOSTNAME}:{PORT}")
        await server.serve()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        global_kill_flag.value = True
        if server:
            server.should_exit = True
            await await_1s()

        process_registry.shutdown_all()
        logger.success("Done! Thank you for using SkellyCam 💀📸✨")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        os._exit(1)
    print("Done!")
    os._exit(0)


