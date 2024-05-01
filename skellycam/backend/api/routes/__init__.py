from skellycam.backend.api.routes.camera_router import camera_router
from skellycam.backend.api.routes.connect_websocket import cam_ws_router
from skellycam.backend.api.routes.health import healthcheck_router
from skellycam.backend.api.routes.startup import startup_router

enabled_routers = [healthcheck_router, camera_router, cam_ws_router, startup_router]