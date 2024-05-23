from skellycam.api.routes.http.close import camera_close_router
from skellycam.api.routes.http.connect import camera_connection_router
from skellycam.api.routes.http.detect import detect_cameras_router
from skellycam.api.routes.http.health import healthcheck_router
from skellycam.api.routes.websocket.websocket_server import websocket_router

enabled_routers = {
    "healthcheck": healthcheck_router,
    "detect_cameras": detect_cameras_router,
    "camera_connection": camera_connection_router,
    "camera_close": camera_close_router,
    "websocket": websocket_router,
}