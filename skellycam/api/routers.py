from skellycam.api.http.app.health import health_router
from skellycam.api.http.app.shutdown import app_shutdown_router
from skellycam.api.http.app.state import state_router
from skellycam.api.http.cameras.camera_router import camera_router
from skellycam.api.http.ui.ui_router import ui_router
from skellycam.api.http.videos.videos_router import load_videos_router
from skellycam.api.websocket.websocket_connect import websocket_router

SKELLYCAM_ROUTES = {
    "/skellycam/ui": {
        "ui": ui_router
    },
    "/skellycam/app": {
        "health": health_router,
        "state": state_router,
        "shutdown": app_shutdown_router
    },
    "/skellycam/websocket": {
        "connect": websocket_router
    },
    "/skellycam/cameras": {
        "connect": camera_router
    },
    "/skellycam/videos": {
        "load": load_videos_router,
    }
}
