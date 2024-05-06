from skellycam.api.endpoints.close import camera_close_router
from skellycam.api.endpoints.connect import camera_connection_router
from skellycam.api.endpoints.detect import detect_cameras_router
from skellycam.api.endpoints.health import healthcheck_router
from skellycam.api.events.startup import startup_router
from skellycam.api.websocket.websocket_server import websocket_router

enabled_routers = {
    "healthcheck": healthcheck_router,
    "startup": startup_router,
    "detect_cameras": detect_cameras_router,
    "camera_connection": camera_connection_router,
    "camera_close": camera_close_router,
    "websocket": websocket_router,
}