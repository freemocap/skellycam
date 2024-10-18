import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
app_shutdown_router = APIRouter()


@app_shutdown_router.get("/shutdown", summary="goodbye👋")
def shutdown_server():
    from skellycam.api.server.server_singleton import get_server_manager
    from skellycam.app.app_controller.app_controller import get_app_controller
    logger.api("Shutdown requested - Closing camera connections and shutting down server...")
    get_app_controller().close()

    get_server_manager().shutdown_server()
    logger.api("Server shutdown complete - Killing process... Bye!👋")
