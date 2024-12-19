from skellycam.api.http.app.health import health_router
from skellycam.api.http.app.shutdown import app_shutdown_router
from skellycam.api.http.app.state import state_router
from skellycam.api.http.cameras.close import close_cameras_router
from skellycam.api.http.cameras.connect import connect_cameras_router
from skellycam.api.http.cameras.record import record_cameras_router
from skellycam.api.http.ui.ui_router import ui_router
from skellycam.api.websocket.websocket_connect import websocket_router

SKELLYCAM_ROUTERS = {
    "/skellycam/cameras": {
        "connect": connect_cameras_router,
        # "detect": detect_cameras_router,
        "record": record_cameras_router,
        "close": close_cameras_router
    },

}

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
    **SKELLYCAM_ROUTERS
}
