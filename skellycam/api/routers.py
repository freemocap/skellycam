from skellycam.api.http.cameras.camera_router import camera_router
from skellycam.api.websocket.websocket_connect import websocket_router

SKELLYCAM_ROUTERS = [
    websocket_router,
    camera_router,
]
