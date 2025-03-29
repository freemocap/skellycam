import logging

from fastapi import APIRouter

from skellycam.skellycam_app.skellycam_app import get_skellycam_app

logger = logging.getLogger(__name__)
app_shutdown_router = APIRouter()


@app_shutdown_router.get("/shutdown", summary="goodbye👋", tags=['App'])
def shutdown_server():
    from skellycam.api.server.server_singleton import get_server_manager
    logger.api("Shutdown requested - Closing camera connections and shutting down server...")
    get_skellycam_app().shutdown_skellycam()

    get_server_manager().shutdown_server()
    logger.api("Server shutdown complete - Killing process... Bye!👋")
