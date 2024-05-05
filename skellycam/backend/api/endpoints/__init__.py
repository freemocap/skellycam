from skellycam.backend.api.endpoints.close import camera_close_router
from skellycam.backend.api.endpoints.connect import camera_connection_router
from skellycam.backend.api.endpoints.detect import detect_cameras_router
from skellycam.backend.api.endpoints.health import healthcheck_router
from skellycam.backend.api.endpoints.startup import startup_router
from skellycam.backend.api.websocket.websocket_server import websocket_router

enabled_routers = [healthcheck_router,
                   startup_router,
                   websocket_router,
                   detect_cameras_router,
                   camera_connection_router,
                   camera_close_router,
                   ]
