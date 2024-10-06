import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
app_shutdown_router = APIRouter()


@app_shutdown_router.get("/shutdown", summary="goodbye👋")
async def shutdown_server():
    from skellycam.api.server.server_singleton import get_server_manager
    from skellycam.core.controller import get_controller
    logger.api("Shutdown requested - Closing camera connections and shutting down server...")
    await get_controller().close_cameras()

    get_server_manager().shutdown_server()
    logger.api("Server shutdown complete - Killing process... Bye!👋")
