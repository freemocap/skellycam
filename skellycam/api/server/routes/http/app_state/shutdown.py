import logging
import os
import signal

from fastapi import APIRouter

from skellycam.api.server.run_server import get_server_manager
from skellycam.core.controller import get_controller

logger = logging.getLogger(__name__)
shutdown_router = APIRouter()


@shutdown_router.get("/shutdown", summary="goodbye👋")
async def shutdown_server():
    logger.api("Shutdown requested - Closing camera connections and shutting down server...")
    await get_controller().close()
    get_server_manager().shutdown_server()
    logger.api("Server shutdown complete - Killing process... Bye!👋")
    os.kill(os.getpid(), signal.SIGINT)
