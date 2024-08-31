import logging
import os
import signal

from fastapi import APIRouter

from skellycam.core.controller import get_controller

logger = logging.getLogger(__name__)
shutdown_router = APIRouter()


@shutdown_router.get("/shutdown", summary="goodbye👋")
async def shutdown_server():
    logger.api("Shutdown requested - Closing camera connections and shutting down server...")
    await get_controller().close_cameras()
    logger.api("Server shutdown complete - Killing process... Bye!👋")
    os.kill(os.getpid(), signal.SIGINT)
