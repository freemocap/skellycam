
import asyncio
import logging
import multiprocessing

import uvicorn

from skellycam.skellycam_app.skellycam_app_factory import create_fastapi_app
from skellycam.utilities.kill_process_on_port import kill_process_on_port
from skellycam.api.server.server_constants import HOSTNAME, PORT
logger = logging.getLogger(__name__)


class ServerManager:
    """Clean async server manager without threading complexity."""

    def __init__(
            self,
            global_kill_flag: multiprocessing.Value,
            hostname: str = HOSTNAME,
            port: int = PORT,
            log_level: str = "info"
    ):
        self.global_kill_flag: multiprocessing.Value = global_kill_flag
        self.hostname: str = hostname
        self.port: int = port
        self.log_level: str = log_level
        self.server: uvicorn.Server|None = None
        self._server_task: asyncio.Task|None = None

    async def run_async(self) -> None:
        """Run the server asynchronously."""
        try:
            # Clean up any existing process on the port
            kill_process_on_port(port=self.port)

            # Create FastAPI app
            app = create_fastapi_app(global_kill_flag=self.global_kill_flag)

            # Configure Uvicorn
            config = uvicorn.Config(
                app=app,
                host=self.hostname,
                port=self.port,
                log_level=self.log_level,
                reload=False,  # Don't use reload in production
                access_log=False,  # Reduce logging noise
            )

            self.server = uvicorn.Server(config)

            logger.info(f"Starting server on {self.hostname}:{self.port}")

            # Run server (this will block until shutdown)
            await self.server.serve()

        except asyncio.CancelledError:
            logger.info("Server task cancelled")
            raise
        except Exception as e:
            logger.error(f"Server error: {e}")
            self.global_kill_flag.value = True
            raise
        finally:
            logger.info("Server stopped")

    async def shutdown(self) -> None:
        """Gracefully shutdown the server."""
        logger.info("Shutting down server...")

        if self.server:
            self.server.should_exit = True
            # Give server time to shutdown gracefully
            await asyncio.sleep(0.5)

        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass

        logger.info("Server shutdown complete")


