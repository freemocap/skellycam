from skellycam.api.http.devices.devices_router import devices_router
from skellycam.api.http.camera_group.camera_group_router import camera_group_router
from skellycam.api.http.recordings.recordings_router import recordings_router
from skellycam.api.websocket.websocket_router import websocket_router

SKELLYCAM_ROUTERS = [
    websocket_router,
    devices_router,
    camera_group_router,
    recordings_router,
]
