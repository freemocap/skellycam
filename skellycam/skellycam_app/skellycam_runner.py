import asyncio
import multiprocessing
import signal
import sys
from contextlib import suppress

import logging
from skellycam.api.server.server_manager import ServerManager


logger = logging.getLogger(__name__)
class SkellyCamRunner:
    """Main application runner with clean lifecycle management."""

    def __init__(self):
        self.global_kill_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self.server_manager: ServerManager|None = None
        self._shutdown_event: asyncio.Event = asyncio.Event()

    async def run(self) -> None:
        """Main async entry point."""
        try:
            # Setup signal handlers
            self._setup_signal_handlers()

            # Create and start server
            logger.info("Starting SkellyCam server...")
            self.server_manager = ServerManager(global_kill_flag=self.global_kill_flag)

            # Run server in background task
            server_task = asyncio.create_task(self.server_manager.run_async())

            # Wait for shutdown signal
            await self._wait_for_shutdown()

            # Graceful shutdown
            await self._shutdown()

            # Wait for server to finish
            with suppress(asyncio.CancelledError):
                await server_task

        except Exception as e:
            logger.error(f"Fatal error in main process: {e}")
            self.global_kill_flag.value = True
            raise
        finally:
            logger.success("Done! Thank you for using SkellyCam 💀📸✨")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()

        def signal_handler(sig: int) -> None:
            logger.info(f"Received signal {sig}, initiating shutdown...")
            self.global_kill_flag.value = True
            self._shutdown_event.set()

        # Register signal handlers for Unix-like systems
        if sys.platform != "win32":
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
        else:
            # Windows doesn't support add_signal_handler, use traditional approach
            signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s))
            signal.signal(signal.SIGINT, lambda s, f: signal_handler(s))

    async def _wait_for_shutdown(self) -> None:
        """Wait for shutdown signal from various sources."""
        # Create tasks for different shutdown conditions
        tasks = [
            asyncio.create_task(self._shutdown_event.wait()),
            asyncio.create_task(self._monitor_kill_flag()),
        ]

        # Wait for any shutdown condition
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _monitor_kill_flag(self) -> None:
        """Monitor the global kill flag."""
        while not self.global_kill_flag.value:
            await asyncio.sleep(0.5)
        logger.info("Global kill flag detected")

    async def _shutdown(self) -> None:
        """Perform graceful shutdown."""
        logger.info("Initiating graceful shutdown...")

        # Set kill flag to notify all processes
        self.global_kill_flag.value = True

        # Shutdown server if it exists
        if self.server_manager:
            await self.server_manager.shutdown()

        logger.info("Shutdown complete")
