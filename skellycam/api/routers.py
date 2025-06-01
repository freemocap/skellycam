from skellycam.api.http.app.health import health_router
from skellycam.api.http.app.shutdown import app_shutdown_router
from skellycam.api.http.app.state import state_router
from skellycam.api.http.cameras.camera_router import camera_router
from skellycam.api.http.ui.ui_router import ui_router
from skellycam.api.http.videos.videos_router import load_videos_router
from skellycam.api.websocket.websocket_connect import websocket_router

SKELLYCAM_ROUTERS = [
    websocket_router,
    camera_router,
    load_videos_router,
]
