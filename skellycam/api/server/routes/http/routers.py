from skellycam.api.server.routes.http.app_state.health import healthcheck_router
from skellycam.api.server.routes.http.app_state.shutdown import shutdown_router
from skellycam.api.server.routes.http.cameras.close import close_cameras_router
from skellycam.api.server.routes.http.cameras.connect import connect_cameras_router
from skellycam.api.server.routes.http.cameras.detect import detect_cameras_router
from skellycam.api.server.routes.websocket.websocket_server import websocket_router

enabled_routers = {
    "/cameras": {
        "connect": connect_cameras_router,
        "detect": detect_cameras_router,
        "close": close_cameras_router
    },
    "/app": {
        "healthcheck": healthcheck_router,
        "shutdown": shutdown_router
    },
    "/ws": {
        "connect": websocket_router
    }
}
