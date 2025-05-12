from skellycam import SKELLYCAM_ROUTERS
from skellycam.api.http.app.health import health_router
from skellycam.api.http.app.shutdown import app_shutdown_router
from skellycam.api.http.app.state import state_router
from skellycam.api.http.cameras.cameras_connect_router import connect_cameras_router
from skellycam.api.http.cameras.cameras_record_router import record_cameras_router
from skellycam.api.http.ui.ui_router import ui_router
from skellycam.api.http.videos.videos_router import load_videos_router
from skellycam.api.websocket.websocket_connect import websocket_router

SKELLYCAM_STANDALONE_ROUTES = {
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
        "connect": connect_cameras_router,
        "record": record_cameras_router
    },
    "/skellycam/videos": {
        "load": load_videos_router,
    }
}
